cmake_minimum_required(VERSION 3.16)
project(roadpilot_native_f8_original_full_receiver LANGUAGES CXX)

# Separate native build: do NOT change the SHA-reviewed Valhalla 3.6.3
# original route/endpoint build recipe in native-f8-edge-scan/CMakeLists.txt.
find_package(PkgConfig REQUIRED)
pkg_check_modules(VALHALLA REQUIRED IMPORTED_TARGET libvalhalla)
add_executable(native_f8_full_receiver_nearpoint
  ../native-f8-edge-scan/native_f8_full_receiver_nearpoint.cpp)
target_compile_features(native_f8_full_receiver_nearpoint PRIVATE cxx_std_20)
target_link_libraries(native_f8_full_receiver_nearpoint PRIVATE PkgConfig::VALHALLA)
target_compile_definitions(native_f8_full_receiver_nearpoint PRIVATE ROADPILOT_VALHALLA_VERSION="${VALHALLA_VERSION}")
target_compile_options(native_f8_full_receiver_nearpoint PRIVATE -Wall -Wextra -Wpedantic)

# Exhaustive ORIGINAL source-archive directed road census, spatially scoped
# to SHA-verified buffered seam cells. No named-road or OSM-way grouping.
add_executable(native_f8_full_source_cut_edges native_f8_full_source_cut_edges.cpp)
target_compile_features(native_f8_full_source_cut_edges PRIVATE cxx_std_20)
target_link_libraries(native_f8_full_source_cut_edges PRIVATE PkgConfig::VALHALLA)
target_compile_definitions(native_f8_full_source_cut_edges PRIVATE ROADPILOT_VALHALLA_VERSION="${VALHALLA_VERSION}")
target_compile_options(native_f8_full_source_cut_edges PRIVATE -Wall -Wextra -Wpedantic)
