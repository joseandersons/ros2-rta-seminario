cmake_minimum_required(VERSION 3.8)
project(polling_demo)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

add_executable(polling_demo src/polling_demo.cpp)
ament_target_dependencies(polling_demo rclcpp std_msgs std_srvs)

install(TARGETS polling_demo DESTINATION lib/${PROJECT_NAME})

ament_package()
