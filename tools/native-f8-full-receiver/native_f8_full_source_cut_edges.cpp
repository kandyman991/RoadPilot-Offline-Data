// Exhaustive ORIGINAL SOURCE Valhalla 3.6.3 directed-road edge census.
// Visits every original GraphReader tile and directed index; no OSM way/name,
// no 512 cap, no Android route discovery, no peer GraphId correlation.
// A sparse metric-buffer grid is a conservative *output* prefilter around the
// original 25-km cutoff. All candidate direction/shape checks are deferred to
// the Python source census, never declared proven by this extractor.
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/baldr/graphconstants.h>
#include <valhalla/midgard/logging.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>

#ifndef ROADPILOT_VALHALLA_VERSION
#error Requires exact native Valhalla version from pkg-config
#endif
namespace {
constexpr double kGridDegree = .01; // ~1 km cells in latitude; output prefilter
constexpr uint64_t kMaxGridCells = 200000;
int grid(double value) {
  if (!std::isfinite(value)) throw std::invalid_argument("Nonfinite coordinate");
  return static_cast<int>(std::floor(value/kGridDegree));
}
uint64_t key(int lat, int lon) {
  return (static_cast<uint64_t>(static_cast<uint32_t>(lat))<<32)
         | static_cast<uint32_t>(lon);
}
uint64_t point_key(double lat, double lon) {
  return key(grid(lat),grid(lon));
}
std::unordered_set<uint64_t> read_cells(const char* filename) {
  std::ifstream in(filename);
  if (!in) throw std::runtime_error("Missing exact buffered seam cells");
  std::unordered_set<uint64_t> cells;
  std::string line;
  while (std::getline(in,line)) {
    std::istringstream ss(line);
    int a,b; std::string rest;
    if (!(ss>>a>>b) || ss>>rest || a < -9000 || a > 9000 ||
        b < -18000 || b > 18000)
      throw std::runtime_error("Malformed integer lat/lon grid cell row");
    if (!cells.insert(key(a,b)).second)
      throw std::runtime_error("Duplicated seam grid cell");
    if (cells.size()>kMaxGridCells)
      throw std::runtime_error("Unbounded seam grid cells");
  }
  if (cells.empty() || !in.eof()) throw std::runtime_error("No valid seam cells");
  return cells;
}
bool eligible_shape(const std::vector<valhalla::midgard::PointLL>& shape,
                    const std::unordered_set<uint64_t>& cells) {
  // Check every vertex AND interpolate every long segment at <~500m.
  // A road that crosses the seam with vertices well outside the buffer
  // cannot be silently lost by a point-only endpoint census.
  if (shape.size()<2) return false;
  for (size_t i=0;i<shape.size();++i) {
    const auto &a=shape[i];
    if (cells.count(point_key(a.lat(),a.lng()))) return true;
    if (!i) continue;
    const auto &b=shape[i-1];
    const double dy=std::abs(a.lat()-b.lat()), dx=std::abs(a.lng()-b.lng());
    const int steps=static_cast<int>(std::ceil(std::max(dx,dy)/.004));
    if (steps>25000) throw std::runtime_error("Unbounded long directed road segment");
    for (int j=1;j<steps;++j) {
      const double part=static_cast<double>(j)/steps;
      if (cells.count(point_key(b.lat()+part*(a.lat()-b.lat()),
                                b.lng()+part*(a.lng()-b.lng()))))
        return true;
    }
  }
  return false;
}
}
int main(int argc,char **argv) {
  if (argc==2 && std::string(argv[1])=="--version") {
    std::cout<<ROADPILOT_VALHALLA_VERSION<<'\n';return 0;
  }
  if (argc!=3) {
    std::cerr<<"usage: native_f8_full_source_cut_edges <valhalla.json> <seam-cells.txt>\n";
    return 64;
  }
  try {
    valhalla::midgard::logging::Configure({{"type","std_err"},{"color","false"}});
    const auto cells=read_cells(argv[2]);
    boost::property_tree::ptree config;
    boost::property_tree::read_json(argv[1],config);
    valhalla::baldr::GraphReader reader(config.get_child("mjolnir"));
    const auto all=reader.GetTileSet();
    if (all.empty()) throw std::runtime_error("No original graph archive tiles");
    uint64_t tiles=0,all_directed=0,roads=0,shapes=0,selected=0,segments=0;
    std::cout<<std::setprecision(11);
    for (const auto& tile_id : all) {
      auto tile=reader.GetGraphTile(tile_id);
      if (!tile) throw std::runtime_error("A source tile is absent from GetTileSet");
      ++tiles;
      for (uint32_t index=0;index<tile->header()->directededgecount();++index) {
        ++all_directed;
        const valhalla::baldr::GraphId id(tile->id().tileid(),
                                          tile->id().level(),index);
        const auto* edge=tile->directededge(id);
        // Valhalla can route mode-accessible original edges with is_road=false.
        // A real F8 A-LAST TripLeg may use such an edge at the graph cut;
        // treating the native is_road flag as exclusion silently loses them.
        // Retain all mode-accessible nonshortcuts, annotate road/use for later
        // ORIGINAL route verification. Never certify from this bit alone.
        if (edge->is_shortcut() ||
            !(edge->forwardaccess() & (valhalla::baldr::kAutoAccess |
                                      valhalla::baldr::kMotorcycleAccess))) continue;
        ++roads;
        auto shape=tile->edgeinfo(edge).shape();
        if (shape.size()<2) continue;
        if (!edge->forward()) std::reverse(shape.begin(),shape.end());
        ++shapes;
        segments+=shape.size()-1;
        if (!eligible_shape(shape,cells)) continue;
        const auto& start=shape.front();
        const auto& end=shape.back();
        if (!std::isfinite(end.lat()) || !std::isfinite(end.lng()))
          throw std::runtime_error("Invalid original source directed endpoint");
        std::cout<<"{\"type\":\"edge\",\"originalDirectedGraphId\":"<<id.value
                 <<",\"originalEndNodeGraphId\":"<<edge->endnode().value
                 <<",\"nativeDeadend\":"<<(edge->deadend()?"true":"false")
                 <<",\"nativeIsRoad\":"<<(edge->is_road()?"true":"false")
                 <<",\"nativeUse\":"<<static_cast<uint32_t>(edge->use())
                 <<",\"originalWayIdAnnotationOnly\":"<<tile->edgeinfo(edge).wayid()
                 <<",\"forwardAccess\":"<<edge->forwardaccess()
                 <<",\"reverseAccess\":"<<edge->reverseaccess()
                 <<",\"directedStart\":["<<start.lat()<<','<<start.lng()
                 <<"],\"directedEnd\":["<<end.lat()<<','<<end.lng()
                 <<"],\"forwardNative\":"<<(edge->forward()?"true":"false")
                 <<"}\n";
        ++selected;
      }
    }
    if (tiles!=all.size()) throw std::runtime_error("Original tile scan incomplete");
    // Emit END only after the complete ORIGINAL archive was read.
    std::cout<<"{\"type\":\"complete\",\"schema\":\"roadpilot.f8-original-source-all-tiles-near-cut\","
                "\"version\":1,\"valhallaVersion\":\""<<ROADPILOT_VALHALLA_VERSION
             <<"\",\"allGraphReaderTilesExhaustivelyRead\":true,"
                "\"originalSourceTileCount\":"<<tiles
             <<",\"allOriginalDirectedGraphIdsVisited\":"<<all_directed
             <<",\"routableRoadDirectedEdgesVisited\":"<<roads
             <<",\"routableShapesVisited\":"<<shapes
             <<",\"routableShapeSegmentsVisited\":"<<segments
             <<",\"originalDirectedEdgesInsideSeamPrefilter\":"<<selected
             <<",\"scannedSeamGridCells\":"<<cells.size()<<"}\n";
    if (!std::cout) throw std::runtime_error("Full source census output write failed");
    return 0;
  } catch(const std::exception& e) {
    std::cerr<<"native_f8_full_source_cut_edges: "<<e.what()
             <<"\nPARTIAL_OUTPUT_INVALID\n";
    return 2;
  }
}
