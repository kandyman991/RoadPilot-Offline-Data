cmake_minimum_required(VERSION 3.16)
project(roadpilot_native_f8_boundary_final LANGUAGES CXX)

find_package(PkgConfig REQUIRED)
pkg_check_modules(VALHALLA REQUIRED IMPORTED_TARGET libvalhalla)

# New D-017 source stage, independent from pinned legacy/native tools.
add_executable(native_f8_boundary_final_edges native_f8_boundary_final_edges.cpp)
target_compile_features(native_f8_boundary_final_edges PRIVATE cxx_std_20)
target_link_libraries(native_f8_boundary_final_edges PRIVATE PkgConfig::VALHALLA)
target_compile_definitions(native_f8_boundary_final_edges PRIVATE ROADPILOT_VALHALLA_VERSION="${VALHALLA_VERSION}")
target_compile_options(native_f8_boundary_final_edges PRIVATE -Wall -Wextra -Wpedantic)
