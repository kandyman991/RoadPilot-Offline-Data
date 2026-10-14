// Read-only, uncapped Valhalla directed-edge window scan for Graph Studio.
// F8-equivalent eligibility predicates transcribed from RoadPilot Android's
// builder_jni.cpp::scan_boundary_road_edges. NOT a capture from Android F8.
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <valhalla/baldr/graphconstants.h>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/baldr/tilehierarchy.h>
#include <valhalla/midgard/aabb2.h>
#include <valhalla/midgard/logging.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef ROADPILOT_VALHALLA_VERSION
#error Build this scanner via its CMakeLists.txt to bind the exact libvalhalla version
#endif

namespace {
double metres(double lat1, double lon1, double lat2, double lon2) {
  constexpr double scale = 111320.0;
  constexpr double pi = 3.14159265358979323846;
  const double mean = (lat1 + lat2) * 0.5 * pi / 180.0;
  const double dy = (lat2 - lat1) * scale;
  const double dx = (lon2 - lon1) * scale * std::cos(mean);
  return std::sqrt(dx * dx + dy * dy);
}

struct point {
  double lat;
  double lon;
};

point routable_point_on_edge(const std::vector<valhalla::midgard::PointLL>& shape,
                            double fallback_lat, double fallback_lon) {
  if (shape.size() < 2) return {fallback_lat, fallback_lon};
  double total = 0;
  for (size_t i = 1; i < shape.size(); ++i)
    total += metres(shape[i - 1].lat(), shape[i - 1].lng(),
                    shape[i].lat(), shape[i].lng());
  if (total <= 1.) return {fallback_lat, fallback_lon};
  const double target = std::min(120.0, total * 0.5);
  double travelled = 0;
  for (size_t i = 1; i < shape.size(); ++i) {
    const auto& a = shape[i - 1];
    const auto& b = shape[i];
    const double segment = metres(a.lat(), a.lng(), b.lat(), b.lng());
    if (segment <= 0.01) continue;
    if (travelled + segment >= target) {
      const double fraction = (target - travelled) / segment;
      return {a.lat() + (b.lat() - a.lat()) * fraction,
              a.lng() + (b.lng() - a.lng()) * fraction};
    }
    travelled += segment;
  }
  return {shape.back().lat(), shape.back().lng()};
}

double parse_bound(const char* raw) {
  const std::string input(raw);
  size_t used = 0;
  const double value = std::stod(input, &used);
  if (used != input.size() || !std::isfinite(value))
    throw std::invalid_argument("Non-finite or invalid bbox coordinate");
  return value;
}
}  // namespace

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--version") {
    std::cout << ROADPILOT_VALHALLA_VERSION << '\n';
    return 0;
  }
  if (argc != 6) {
    std::cerr << "usage: native_f8_edge_scan <valhalla.json> <minLat> <maxLat> <minLon> <maxLon>\n";
    return 64;
  }
  try {
    // Valhalla defaults to stdout logging, which corrupts machine-readable JSON.
    valhalla::midgard::logging::Configure({{"type", "std_err"}, {"color", "false"}});
    const double min_lat = parse_bound(argv[2]);
    const double max_lat = parse_bound(argv[3]);
    const double min_lon = parse_bound(argv[4]);
    const double max_lon = parse_bound(argv[5]);
    if (!(min_lat < max_lat && min_lon < max_lon) ||
        min_lat < -90 || max_lat > 90 || min_lon < -180 || max_lon > 180)
      throw std::invalid_argument("Invalid scan rectangle");

    boost::property_tree::ptree config;
    boost::property_tree::read_json(argv[1], config);
    // Use the exact Graph Studio-generated Valhalla config, including its
    // tile_extract; do not unpack/rebuild or modify retained .gph files.
    valhalla::baldr::GraphReader reader(config.get_child("mjolnir"));
    const valhalla::midgard::AABB2<valhalla::midgard::PointLL> bbox(
        min_lon, min_lat, max_lon, max_lat);
    uint64_t tiles = 0, nodes = 0, emitted = 0;
    bool first = true;
    std::cout << std::setprecision(11);
    std::cout << "{\"schema\":\"roadpilot.graph-studio-native-edge-window\","
                 "\"version\":1,\"scanner\":\"GraphStudio.nativeUncappedRoadEdges\","
                 "\"valhallaVersion\":\"" << ROADPILOT_VALHALLA_VERSION
              << "\",\"edges\":[";
    for (const auto& level : valhalla::baldr::TileHierarchy::levels()) {
      for (const auto id : level.tiles.TileList(bbox)) {
        const valhalla::baldr::GraphId tile_id(
            static_cast<uint32_t>(id), level.level, 0);
        if (!reader.DoesTileExist(tile_id)) continue;
        auto tile = reader.GetGraphTile(tile_id);
        if (!tile) throw std::runtime_error("A declared graph tile failed to load");
        ++tiles;
        const auto* header = tile->header();
        for (uint32_t node_index = 0; node_index < header->nodecount(); ++node_index) {
          const valhalla::baldr::GraphId node_id(
              tile->id().tileid(), tile->id().level(), node_index);
          const auto ll = tile->get_node_ll(node_id);
          const double lat = ll.lat();
          const double lon = ll.lng();
          if (lat < min_lat || lat > max_lat || lon < min_lon || lon > max_lon)
            continue;
          ++nodes;
          const auto* node = tile->node(node_index);
          for (uint32_t offset = 0; offset < node->edge_count(); ++offset) {
            const valhalla::baldr::GraphId edge_id(
                tile->id().tileid(), tile->id().level(), node->edge_index() + offset);
            const auto* edge = tile->directededge(edge_id);
            if (edge->is_shortcut() || edge->IsTransitLine() ||
                (!edge->is_road() && edge->use() != valhalla::baldr::Use::kFerry))
              continue;
            const uint32_t forward_access = edge->forwardaccess();
            const uint32_t reverse_access = edge->reverseaccess();
            if (((forward_access | reverse_access) &
                 (valhalla::baldr::kMotorcycleAccess | valhalla::baldr::kAutoAccess)) == 0)
              continue;
            const auto info = tile->edgeinfo(edge);
            const uint64_t way_id = info.wayid();
            if (way_id == 0) continue;
            auto shape = info.shape();
            if (!edge->forward()) std::reverse(shape.begin(), shape.end());
            const auto inner = routable_point_on_edge(shape, lat, lon);
            if (metres(lat, lon, inner.lat, inner.lon) < 1.0) continue;
            if (!first) std::cout << ',';
            first = false;
            std::cout << "{\"graphId\":" << edge_id.value
                      << ",\"wayId\":" << way_id
                      << ",\"lat\":" << lat << ",\"lon\":" << lon
                      << ",\"innerLat\":" << inner.lat
                      << ",\"innerLon\":" << inner.lon
                      << ",\"forwardAccess\":" << forward_access
                      << ",\"reverseAccess\":" << reverse_access
                      << ",\"roadClass\":" << static_cast<uint32_t>(edge->classification())
                      << ",\"use\":" << static_cast<uint32_t>(edge->use())
                      << ",\"toll\":" << (edge->toll() ? "true" : "false")
                      << ",\"tunnel\":" << (edge->tunnel() ? "true" : "false")
                      << ",\"unpaved\":" << (edge->unpaved() ? "true" : "false")
                      << '}';
            ++emitted;
          }
        }
      }
    }
    std::cout << "],\"returned\":" << emitted
              << ",\"visitedTiles\":" << tiles
              << ",\"visitedNodes\":" << nodes
              << ",\"complete\":true,\"truncated\":false,\"maxResults\":null}\n";
    if (!std::cout) throw std::runtime_error("Native graph edge output write failed");
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "native_f8_edge_scan failed: " << error.what() << '\n';
    // Partial stdout is invalid JSON; the Python producer never commits it.
    return 2;
  }
}
