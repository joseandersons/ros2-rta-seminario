cmake_minimum_required(VERSION 3.5)

project(model_validation)
add_compile_options(-g -Wall -Wextra)
set(CMAKE_CXX_STANDARD 17)  # [Jazzy] rclcpp exige C++17

find_package(ament_cmake_auto REQUIRED)
ament_auto_find_build_dependencies()
# [Jazzy] a função generate_interfaces() do original usava APIs removidas
# (rosidl_target_interfaces); aqui as interfaces são ligadas do jeito atual.
find_package(rosidl_default_generators REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME} "msg/Duration.msg" "srv/Duration.srv" "srv/Int32.srv")
ament_auto_add_executable(arbitrary_cb_time src/arbitrary_cb_time.cpp)
rosidl_get_typesupport_target(cpp_typesupport_target ${PROJECT_NAME} "rosidl_typesupport_cpp")
target_link_libraries(arbitrary_cb_time "${cpp_typesupport_target}")

install(DIRECTORY bin/ DESTINATION bin
  FILE_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE)
ament_auto_package(INSTALL_TO_PATH)
