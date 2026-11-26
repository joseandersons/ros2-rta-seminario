// Reprodução do experimento de validação (Seção 3, Fig. 3) de
// Casini et al., ECRTS 2019, num ROS 2 atual.
//
// Nó "experimento" (executado pelo executor sob teste):
//   - 3 subscribers  H, M, L   (registrados nesta ordem)
//   - 3 services     SH, SM, SL (registrados nesta ordem)
//   - 4 timers one-shot: t0, t1 em 200 ms e t2, t3 em 2300 ms
//   Toda callback ocupa a CPU por 500 ms (busy-wait).
//
// Nó "driver" (outra thread, não é executado pelo executor sob teste):
//   - em t = 0       envia  <L M H SH SL L M H SH SL>
//   - em t = 1500 ms envia  <SM SM H>
//
// Saída: trace.csv com  evento,nome,inicio_ms,fim_ms
//   evento = "run"    -> execução de callback
//   evento = "arrive" -> chegada (envio) da mensagem/request
//
// Uso: ros2 run polling_demo polling_demo [single|multi|events]
#include <atomic>
#include <chrono>
#include <fstream>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/empty.hpp"
#include "std_srvs/srv/empty.hpp"

#if __has_include(<rclcpp/experimental/executors/events_executor/events_executor.hpp>)
#include "rclcpp/experimental/executors/events_executor/events_executor.hpp"
#define HAS_EVENTS_EXECUTOR 1
#endif

using namespace std::chrono_literals;
using Clock = std::chrono::steady_clock;

static Clock::time_point T0;
static std::mutex log_mtx;
static std::ofstream trace;

static double now_ms() {
  return std::chrono::duration<double, std::milli>(Clock::now() - T0).count();
}

static void log_event(const std::string & ev, const std::string & name, double a, double b) {
  std::lock_guard<std::mutex> lk(log_mtx);
  trace << ev << "," << name << "," << a << "," << b << "\n";
  trace.flush();
  printf("%-6s %-4s %8.1f %8.1f\n", ev.c_str(), name.c_str(), a, b);
}

static void busy(const std::string & name, std::chrono::milliseconds dur = 500ms) {
  const double start = now_ms();
  const auto until = Clock::now() + dur;
  while (Clock::now() < until) { /* consome CPU, como uma callback "pesada" */ }
  log_event("run", name, start, now_ms());
}

class Experiment : public rclcpp::Node {
public:
  Experiment() : Node("experiment") {
    auto qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable();
    // Ordem de registro = 2º nível de prioridade dentro da categoria
    for (const char * t : {"H", "M", "L"}) {
      std::string name = t;
      subs_.push_back(create_subscription<std_msgs::msg::Empty>(
        name, qos, [name](std_msgs::msg::Empty::ConstSharedPtr) { busy(name); }));
    }
    for (const char * s : {"SH", "SM", "SL"}) {
      std::string name = s;
      srvs_.push_back(create_service<std_srvs::srv::Empty>(
        name,
        [name](const std::shared_ptr<std_srvs::srv::Empty::Request>,
               std::shared_ptr<std_srvs::srv::Empty::Response>) { busy(name); }));
    }
  }

  // Timers one-shot, criados exatamente em T0
  void create_timers() {
    const std::vector<std::pair<std::string, std::chrono::milliseconds>> cfg = {
      {"t0", 200ms}, {"t1", 200ms}, {"t2", 2300ms}, {"t3", 2300ms}};
    timers_.resize(cfg.size());
    for (size_t i = 0; i < cfg.size(); ++i) {
      const auto name = cfg[i].first;
      log_event("arrive", name, cfg[i].second.count(), cfg[i].second.count());
      timers_[i] = create_wall_timer(cfg[i].second, [this, i, name]() {
        timers_[i]->cancel();
        busy(name);
      });
    }
  }

private:
  std::vector<rclcpp::Subscription<std_msgs::msg::Empty>::SharedPtr> subs_;
  std::vector<rclcpp::Service<std_srvs::srv::Empty>::SharedPtr> srvs_;
  std::vector<rclcpp::TimerBase::SharedPtr> timers_;
};

class Driver : public rclcpp::Node {
public:
  Driver() : Node("driver") {
    auto qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable();
    for (const char * t : {"H", "M", "L"}) pubs_[t] = create_publisher<std_msgs::msg::Empty>(t, qos);
    for (const char * s : {"SH", "SM", "SL"}) clis_[s] = create_client<std_srvs::srv::Empty>(s);
  }

  void wait_ready() {
    for (auto & [n, c] : clis_) {
      while (!c->wait_for_service(100ms)) RCLCPP_INFO(get_logger(), "aguardando serviço %s", n.c_str());
    }
    for (auto & [n, p] : pubs_) {
      while (p->get_subscription_count() == 0) std::this_thread::sleep_for(50ms);
    }
  }

  void send(const std::string & name) {
    log_event("arrive", name, now_ms(), now_ms());
    if (name[0] == 'S') {
      // resposta ignorada: só importa a request chegar ao service
      clis_[name]->async_send_request(std::make_shared<std_srvs::srv::Empty::Request>());
    } else {
      pubs_[name]->publish(std_msgs::msg::Empty());
    }
  }

  void run() {
    for (auto n : {"L", "M", "H", "SH", "SL", "L", "M", "H", "SH", "SL"}) send(n);
    std::this_thread::sleep_until(T0 + 1500ms);
    for (auto n : {"SM", "SM", "H"}) send(n);
  }

private:
  std::map<std::string, rclcpp::Publisher<std_msgs::msg::Empty>::SharedPtr> pubs_;
  std::map<std::string, rclcpp::Client<std_srvs::srv::Empty>::SharedPtr> clis_;
};

// ---------------------------------------------------------------------------
// Modo "robo": a mesma cena do slide 6 (robô aspirador), com tempos x100.
//   Ler sensor: timer a cada 600 ms, trabalha 200 ms
//   Bateria:    subscriber, trabalha 500 ms
//   Desviar:    subscriber (a urgente), trabalha 300 ms
// Em t = 0 o sensor e a bateria estão prontos (comanda 1).
// Em t = 50 ms chega "parede!" para o Desviar: ele espera a comanda inteira.
// ---------------------------------------------------------------------------
class Robo : public rclcpp::Node {
public:
  Robo() : Node("robo") {
    auto qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable();
    desviar_ = create_subscription<std_msgs::msg::Empty>(
      "parede", qos, [](std_msgs::msg::Empty::ConstSharedPtr) { busy("desviar", 300ms); });
    bateria_ = create_subscription<std_msgs::msg::Empty>(
      "bateria", qos, [](std_msgs::msg::Empty::ConstSharedPtr) { busy("bateria", 500ms); });
  }

  void create_sensor_timer() {
    sensor_ = create_wall_timer(600ms, []() { busy("sensor", 200ms); });
  }

private:
  rclcpp::Subscription<std_msgs::msg::Empty>::SharedPtr desviar_, bateria_;
  rclcpp::TimerBase::SharedPtr sensor_;
};

static int run_robo() {
  auto robo = std::make_shared<Robo>();
  auto mundo = std::make_shared<rclcpp::Node>("mundo");   // quem manda as mensagens
  auto qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable();
  auto pub_parede = mundo->create_publisher<std_msgs::msg::Empty>("parede", qos);
  auto pub_bateria = mundo->create_publisher<std_msgs::msg::Empty>("bateria", qos);
  while (pub_parede->get_subscription_count() == 0 || pub_bateria->get_subscription_count() == 0) {
    std::this_thread::sleep_for(50ms);
  }
  std::this_thread::sleep_for(500ms);

  // O timer é criado 600 ms antes de T0, então ele vence exatamente em T0.
  T0 = Clock::now() + 600ms;
  robo->create_sensor_timer();
  for (int k = 0; k < 3; ++k) log_event("arrive", "sensor", 600.0 * k, 600.0 * k);

  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(robo);

  std::this_thread::sleep_until(T0);
  log_event("arrive", "bateria", now_ms(), now_ms());
  pub_bateria->publish(std_msgs::msg::Empty());
  std::this_thread::sleep_until(T0 + 10ms);   // sensor e bateria já prontos: comanda 1

  std::thread parede([pub_parede]() {
    std::this_thread::sleep_until(T0 + 50ms);
    log_event("arrive", "desviar", now_ms(), now_ms());
    pub_parede->publish(std_msgs::msg::Empty());
  });
  std::thread stopper([&exec]() {
    std::this_thread::sleep_until(T0 + 1500ms);
    exec.cancel();
  });
  printf("evento nome     inicio   fim  (ms, relativos a T0)\n");
  exec.spin();
  parede.join();
  stopper.join();
  return 0;
}

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  const std::string kind = argc > 1 ? argv[1] : "single";

  if (kind == "robo") {
    trace.open("trace_robo.csv");
    trace << "evento,nome,inicio_ms,fim_ms\n";
    run_robo();
    trace.close();
    rclcpp::shutdown();
    printf("\nTrace salvo em trace_robo.csv\n");
    return 0;
  }

  std::shared_ptr<rclcpp::Executor> exec;
  if (kind == "single") {
    exec = std::make_shared<rclcpp::executors::SingleThreadedExecutor>();
  } else if (kind == "multi") {
    exec = std::make_shared<rclcpp::executors::MultiThreadedExecutor>();
#ifdef HAS_EVENTS_EXECUTOR
  } else if (kind == "events") {
    exec = std::make_shared<rclcpp::experimental::executors::EventsExecutor>();
#endif
  } else {
    fprintf(stderr, "executor desconhecido: %s\n", kind.c_str());
    return 1;
  }

  trace.open("trace_" + kind + ".csv");
  trace << "evento,nome,inicio_ms,fim_ms\n";

  auto exp = std::make_shared<Experiment>();
  auto drv = std::make_shared<Driver>();
  drv->wait_ready();   // descoberta DDS concluída antes de começar
  std::this_thread::sleep_for(500ms);

  T0 = Clock::now();
  exp->create_timers();
  exec->add_node(exp);
  std::thread driver_thread([drv]() { drv->run(); });

  printf("evento nome  inicio   fim  (ms, relativos a T0)\n");
  std::thread stopper([exec]() {           // encerra o experimento após 10 s
    std::this_thread::sleep_until(T0 + 10s);
    exec->cancel();
  });
  exec->spin();

  driver_thread.join();
  stopper.join();
  trace.close();
  rclcpp::shutdown();
  printf("\nTrace salvo em trace_%s.csv\n", kind.c_str());
  return 0;
}
