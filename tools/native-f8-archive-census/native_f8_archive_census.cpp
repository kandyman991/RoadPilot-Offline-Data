// Native, read-only Valhalla 3.6.3 archive-wide ORIGINAL directed-edge census.
// Unlike overlap-window scans, this walks EVERY GraphReader::GetTileSet() tile
// and each actual directed edge index. The four coordinate bounds are a
// conservative geographic observation filter ONLY, never road equivalence.
#include <boost/geometry.hpp>
#include <boost/geometry/index/rtree.hpp>
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/midgard/logging.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <fstream>
#include <sstream>
#include <iterator>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef ROADPILOT_VALHALLA_VERSION
#error Requires real Valhalla build version.
#endif

namespace {
namespace bg = boost::geometry;
namespace bgi = boost::geometry::index;
using Point = bg::model::d2::point_xy<double>;
using Box = bg::model::box<Point>;
using RTree = bgi::rtree<Box, bgi::quadratic<16>>;

RTree read_boundary_rectangles(const std::string& path) {
  std::ifstream source(path);
  if (!source) throw std::runtime_error("Cannot read original source boundary rectangle file");
  std::vector<Box> boxes;
  std::string line;
  while (std::getline(source, line)) {
    double a, b, c, d;
    std::istringstream input(line);
    std::string extra;
    if (!(input >> a >> b >> c >> d) || (input >> extra) ||
        !std::isfinite(a) || !std::isfinite(b) ||
        !std::isfinite(c) || !std::isfinite(d) ||
        a < -180 || c > 180 || b < -90 || d > 90 ||
        a >= c || b >= d || boxes.size() >= 20000)
      throw std::runtime_error("Invalid or excessive boundary coverage rectangles");
    boxes.emplace_back(Point(a, b), Point(c, d));
  }
  if (!source.eof() || boxes.empty())
    throw std::runtime_error("Incomplete/empty original buffer boundary rectangle inventory");
  return RTree(boxes);
}
double coordinate(const char* arg, double bound) {
  const std::string value(arg);
  std::size_t consumed = 0;
  double result = std::stod(value, &consumed);
  if (consumed != value.size() || !std::isfinite(result) ||
      std::abs(result) > bound)
    throw std::invalid_argument("Invalid geographic original candidate envelope");
  return result;
}
} // namespace

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--version") {
    std::cout << ROADPILOT_VALHALLA_VERSION << '\n';
    return 0;
  }
  const bool bbox_mode = argc == 7 && std::string(argv[2]) == "--bbox";
  const bool rectangle_mode = argc == 4 && std::string(argv[2]) == "--boundary-rectangles";
  if (!bbox_mode && !rectangle_mode) {
    std::cerr << "usage: native_f8_archive_census <valhalla.json>"
              << " [--bbox west south east north | --boundary-rectangles rectangles.txt]\n";
    return 64;
  }
  try {
    const double west = bbox_mode ? coordinate(argv[3], 180) : -180;
    const double south = bbox_mode ? coordinate(argv[4], 90) : -90;
    const double east = bbox_mode ? coordinate(argv[5], 180) : 180;
    const double north = bbox_mode ? coordinate(argv[6], 90) : 90;
    if (west >= east || south >= north)
      throw std::invalid_argument("Invalid ordered geographic envelope");
    const auto boundary_boxes = rectangle_mode ? read_boundary_rectangles(argv[3]) : RTree();
    valhalla::midgard::logging::Configure({{"type", "std_err"}, {"color", "false"}});
    boost::property_tree::ptree config;
    boost::property_tree::read_json(argv[1], config);
    valhalla::baldr::GraphReader reader(config.get_child("mjolnir"));
    const auto available = reader.GetTileSet();
    if (available.empty()) throw std::runtime_error("Original source graph has no tiles");
    std::vector<valhalla::baldr::GraphId> tiles(available.begin(), available.end());
    std::sort(tiles.begin(), tiles.end(),
              [](const auto& a, const auto& b) { return a.value < b.value; });
    uint64_t total_edges = 0, total_bbox = 0;
    std::cout << std::setprecision(11);
    for (const auto tile_id : tiles) {
      const auto tile = reader.GetGraphTile(tile_id);
      if (!tile || tile->id() != tile_id.tile_base())
        throw std::runtime_error("Original GraphReader tile set returned absent/wrong tile");
      const uint32_t count = tile->header()->directededgecount();
      uint64_t candidates = 0;
      for (uint32_t index = 0; index < count; ++index) {
        const valhalla::baldr::GraphId id(tile_id.tileid(), tile_id.level(), index);
        const auto* edge = tile->directededge(id);
        if (!edge) throw std::runtime_error("Original directed edge unexpectedly missing");
        const auto end_id = edge->endnode();
        if (!end_id.is_valid())
          throw std::runtime_error("Original directed edge has invalid end-node GraphId");
        // Decode every original directed geometry, including both directions,
        // ferries/nonroads, mode-inaccessible edges and shortcuts. NO filtering
        // by way IDs, road names, forward access, hierarchy level or direction.
        auto shape = tile->edgeinfo(edge).shape();
        if (!edge->forward()) std::reverse(shape.begin(), shape.end());
        if (shape.size() < 2)
          throw std::runtime_error("Original directed edge has missing geometry");
        double min_lon = 181, max_lon = -181, min_lat = 91, max_lat = -91;
        for (const auto& point : shape) {
          if (!std::isfinite(point.lng()) || !std::isfinite(point.lat()) ||
              std::abs(point.lng()) > 180 || std::abs(point.lat()) > 90)
            throw std::runtime_error("Original source directed geometry invalid");
          min_lon = std::min(min_lon, point.lng());
          max_lon = std::max(max_lon, point.lng());
          min_lat = std::min(min_lat, point.lat());
          max_lat = std::max(max_lat, point.lat());
        }
        if (max_lon < west || min_lon > east || max_lat < south || min_lat > north)
          continue;
        if (rectangle_mode) {
          const Box original_shape_bbox(Point(min_lon, min_lat), Point(max_lon, max_lat));
          const auto found = boundary_boxes.qbegin(bgi::intersects(original_shape_bbox));
          if (found == boundary_boxes.qend()) continue;
        }
        ++candidates;
        const uint64_t way = tile->edgeinfo(edge).wayid();
        std::cout << "{\"type\":\"candidate\",\"tileGraphId\":"
                  << tile_id.tile_base().value
                  << ",\"originalDirectedGraphId\":" << id.value
                  << ",\"originalEndNodeGraphId\":" << end_id.value
                  << ",\"forwardAccess\":" << edge->forwardaccess()
                  << ",\"reverseAccess\":" << edge->reverseaccess()
                  << ",\"isRoad\":" << (edge->is_road() ? "true" : "false")
                  << ",\"isShortcut\":" << (edge->is_shortcut() ? "true" : "false")
                  << ",\"deadend\":" << (edge->deadend() ? "true" : "false")
                  << ",\"wayIdAnnotationOnly\":" << way
                  << ",\"directedGeometry\":[";
        for (size_t j = 0; j < shape.size(); ++j) {
          if (j) std::cout << ',';
          std::cout << '[' << shape[j].lat() << ',' << shape[j].lng() << ']';
        }
        std::cout << "]}\n";
        if (!std::cout) throw std::runtime_error("Native original directed geometry output failed");
      }
      total_edges += count;
      total_bbox += candidates;
      std::cout << "{\"type\":\"tile\",\"tileGraphId\":"
                << tile_id.tile_base().value
                << ",\"level\":" << static_cast<unsigned>(tile_id.level())
                << ",\"tileId\":" << tile_id.tileid()
                << ",\"nodeCount\":" << tile->header()->nodecount()
                << ",\"originalDirectedCount\":" << count
                << ",\"bboxCandidateCount\":" << candidates << "}\n";
      if (!std::cout) throw std::runtime_error("Original source tile output failed");
    }
    std::cout << "{\"type\":\"summary\",\"valhallaVersion\":\""
              << ROADPILOT_VALHALLA_VERSION << "\",\"archiveTileCount\":"
              << tiles.size() << ",\"allOriginalDirectedCount\":" << total_edges
              << ",\"bboxCandidateCount\":" << total_bbox << "}\n";
    if (!std::cout) throw std::runtime_error("Original native census output failed");
    return 0;
  } catch (const std::exception& exc) {
    std::cerr << "NATIVE_F8_ARCHIVE_CENSUS_FAILED: " << exc.what()
              << "\nPARTIAL_STDOUT_INVALID\n";
    return 2;
  }
}
