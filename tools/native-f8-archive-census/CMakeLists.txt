cmake_minimum_required(VERSION 3.16)
project(roadpilot_native_f8_original_archive_census LANGUAGES CXX)
find_package(PkgConfig REQUIRED)
pkg_check_modules(VALHALLA REQUIRED IMPORTED_TARGET libvalhalla)
# Isolated new archive census target: do NOT mutate the historical SHA-bound
# Valhalla route extractor CMakeLists.txt used in reviewed source provenance.
add_executable(native_f8_archive_census native_f8_archive_census.cpp)
target_compile_features(native_f8_archive_census PRIVATE cxx_std_20)
target_link_libraries(native_f8_archive_census PRIVATE PkgConfig::VALHALLA)
target_compile_definitions(native_f8_archive_census PRIVATE ROADPILOT_VALHALLA_VERSION="${VALHALLA_VERSION}")
target_compile_options(native_f8_archive_census PRIVATE -Wall -Wextra -Wpedantic)
