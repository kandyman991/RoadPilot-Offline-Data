cmake_minimum_required(VERSION 3.20)
project(roadpilot_transition_probe LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(PkgConfig REQUIRED)
pkg_check_modules(VALHALLA REQUIRED IMPORTED_TARGET libvalhalla)
# The pinned host build installs libvalhalla as a static archive. pkg-config's normal
# imported target does not pull LibLZ4 from Libs.private, even though Valhalla's Skadi
# objects reference the LZ4 frame API. Link it explicitly so the standalone RoadPilot
# host tools have the same complete dependency closure as the Valhalla build itself.
pkg_check_modules(LZ4 REQUIRED IMPORTED_TARGET liblz4)

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
    PkgConfig::LZ4
)

target_link_libraries(
    roadpilot-boundary-inventory
    PRIVATE
    PkgConfig::VALHALLA
    PkgConfig::LZ4
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
