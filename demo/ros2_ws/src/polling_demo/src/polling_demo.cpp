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
// Uso: ros2 run polling_demo polling_demo [single]
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
  if (ev != "start") printf("%-6s %-4s %8.1f %8.1f\n", ev.c_str(), name.c_str(), a, b);
}

// Marca T0 no relógio de parede, para a visualização ao vivo (live.py)
// saber quanto tempo passou desde o início do experimento.
static void log_epoch() {
  const double ms = std::chrono::duration<double, std::milli>(
    std::chrono::system_clock::now().time_since_epoch()).count();
  std::lock_guard<std::mutex> lk(log_mtx);
  char buf[64];
  snprintf(buf, sizeof(buf), "%.1f", ms);
  trace << "epoch,T0," << buf << "," << buf << "\n";
  trace.flush();
}

static void busy(const std::string & name) {
  const double start = now_ms();
  log_event("start", name, start, start);   // a callback começou a rodar
  const auto until = Clock::now() + 500ms;
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

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  const std::string kind = argc > 1 ? argv[1] : "single";

  if (kind != "single") {
    fprintf(stderr, "executor desconhecido: %s (use single)\n", kind.c_str());
    return 1;
  }
  // O executor analisado no artigo: single-threaded, com polling points
  auto exec = std::make_shared<rclcpp::executors::SingleThreadedExecutor>();

  trace.open("trace_" + kind + ".csv");
  trace << "evento,nome,inicio_ms,fim_ms\n";

  auto exp = std::make_shared<Experiment>();
  auto drv = std::make_shared<Driver>();
  drv->wait_ready();   // descoberta DDS concluída antes de começar
  std::this_thread::sleep_for(500ms);

  T0 = Clock::now();
  log_epoch();
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
