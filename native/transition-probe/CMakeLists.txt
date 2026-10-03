cmake_minimum_required(VERSION 3.20)
project(roadpilot_transition_probe LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(PkgConfig REQUIRED)
pkg_check_modules(VALHALLA REQUIRED IMPORTED_TARGET libvalhalla)

add_executable(
    roadpilot-transition-probe
    roadpilot_transition_probe.cpp
)

add_executable(
    roadpilot-boundary-inventory
    roadpilot_boundary_inventory.cpp
)

target_link_libraries(
    roadpilot-transition-probe
    PRIVATE
    PkgConfig::VALHALLA
)

target_link_libraries(
    roadpilot-boundary-inventory
    PRIVATE
    PkgConfig::VALHALLA
)

target_compile_options(
    roadpilot-transition-probe
    PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)

target_compile_options(
    roadpilot-boundary-inventory
    PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)
