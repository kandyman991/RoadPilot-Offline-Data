cmake_minimum_required(VERSION 3.16)
project(roadpilot_native_f8_edge_scan LANGUAGES CXX)

find_package(PkgConfig REQUIRED)
pkg_check_modules(VALHALLA REQUIRED IMPORTED_TARGET libvalhalla)

add_executable(native_f8_edge_scan native_f8_edge_scan.cpp)
target_compile_features(native_f8_edge_scan PRIVATE cxx_std_17)
target_link_libraries(native_f8_edge_scan PRIVATE PkgConfig::VALHALLA)
target_compile_options(native_f8_edge_scan PRIVATE -Wall -Wextra -Wpedantic)
