// Immutable ORIGINAL Valhalla receiver GraphReader archive: full directed-shape
// overlap with supplied source last-edge coordinates. NOT a graph-ID match,
// handoff selection, GPS guess, or F8 route proof. Every tile and every
// routable real-road directed edge is scanned; actual Valhalla B-FIRST
// TripLeg checks are separate mandatory gates.
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
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef ROADPILOT_VALHALLA_VERSION
#error "Build with the exact Valhalla 3.6.3 version"
#endif

namespace {
struct Query { uint64_t id; double lat, lon; };
constexpr double kMetresPerDegree = 111320.0;
constexpr double kPi = 3.14159265358979323846;

double parse_double(const std::string& value) {
  if (value.empty()) throw std::invalid_argument("Empty coordinate");
  size_t used = 0;
  const double x = std::stod(value, &used);
  if (used != value.size() || !std::isfinite(x))
    throw std::invalid_argument("Invalid nonfinite coordinate");
  return x;
}
uint64_t parse_id(const std::string& raw) {
  if (raw.empty() || raw.find_first_not_of("0123456789") != std::string::npos)
    throw std::invalid_argument("Invalid unsigned GraphId");
  size_t used = 0;
  const auto x = std::stoull(raw, &used);
  if (used != raw.size() || !x) throw std::invalid_argument("Invalid GraphId");
  return x;
}
std::vector<Query> load_queries(const char* filename) {
  std::ifstream input(filename);
  if (!input) throw std::runtime_error("Missing original source-point CSV");
  std::vector<Query> q;
  std::string line;
  while (std::getline(input,line)) {
    std::istringstream row(line);
    std::string s_id, s_lat, s_lon, extra;
    if (!std::getline(row,s_id,',') || !std::getline(row,s_lat,',') ||
        !std::getline(row,s_lon,',') || std::getline(row,extra,','))
      throw std::invalid_argument("Each source row must be <GraphId>,<lat>,<lon>");
    Query x{parse_id(s_id),parse_double(s_lat),parse_double(s_lon)};
    if (std::abs(x.lat)>90 || std::abs(x.lon)>180)
      throw std::invalid_argument("Invalid source latitude/longitude");
    q.push_back(x);
    if (q.size()>200000)
      throw std::invalid_argument("Excessive source query rows");
  }
  if (!input.eof() || q.empty()) throw std::runtime_error("Empty/truncated query file");
  std::sort(q.begin(),q.end(),[](const Query& a,const Query& b) {
    return a.lat < b.lat || (a.lat==b.lat && a.id < b.id);
  });
  std::vector<uint64_t> ids;
  for (const auto& x:q) ids.push_back(x.id);
  std::sort(ids.begin(),ids.end());
  if (std::adjacent_find(ids.begin(),ids.end())!=ids.end())
    throw std::runtime_error("Duplicated source query GraphId");
  return q;
}
double metres_to_segment(const Query& q,
                         const valhalla::midgard::PointLL& a,
                         const valhalla::midgard::PointLL& b) {
  const double lon_factor = kMetresPerDegree * std::cos(q.lat*kPi/180.0);
  const double ax=(a.lng()-q.lon)*lon_factor, ay=(a.lat()-q.lat)*kMetresPerDegree;
  const double bx=(b.lng()-q.lon)*lon_factor, by=(b.lat()-q.lat)*kMetresPerDegree;
  const double vx=bx-ax, vy=by-ay, len2=vx*vx+vy*vy;
  if (len2<1.e-9) return std::hypot(ax,ay);
  const double t=std::max(0.0,std::min(1.0,-(ax*vx+ay*vy)/len2));
  return std::hypot(ax+t*vx,ay+t*vy);
}
} // namespace

int main(int argc,char** argv) {
  if (argc==2 && std::string(argv[1])=="--version") {
    std::cout << ROADPILOT_VALHALLA_VERSION << '\n';
    return 0;
  }
  if (argc!=4) {
    std::cerr << "usage: native_f8_full_receiver_nearpoint <valhalla.json> <source-final-coordinates.csv> <query-radius-metres>\n";
    return 64;
  }
  try {
    valhalla::midgard::logging::Configure({{"type","std_err"},{"color","false"}});
    const auto q=load_queries(argv[2]);
    const double radius=parse_double(argv[3]);
    if (!(radius>=3.0 && radius<=100.0))
      throw std::invalid_argument("Candidate prefetch radius must be 3..100m");
    boost::property_tree::ptree config;
    boost::property_tree::read_json(argv[1],config);
    valhalla::baldr::GraphReader reader(config.get_child("mjolnir"));
    const auto all=reader.GetTileSet();
    if (all.empty()) throw std::runtime_error("Original receiver graph tile set empty");
    uint64_t scanned=0, directed=0, shapes=0, segments=0;
    std::map<std::pair<uint64_t,uint64_t>,double> matches;
    const double lat_pad=(radius+1.0)/kMetresPerDegree;
    for (const auto& tile_id : all) {
      auto tile=reader.GetGraphTile(tile_id);
      if (!tile) throw std::runtime_error("Original receiver tile in native set absent");
      ++scanned;
      const auto* header=tile->header();
      for (uint32_t i=0;i<header->directededgecount();++i) {
        const valhalla::baldr::GraphId id(tile->id().tileid(),tile->id().level(),i);
        const auto* edge=tile->directededge(id);
        ++directed;
        if (edge->is_shortcut() || !edge->is_road() ||
            !(edge->forwardaccess() & (valhalla::baldr::kAutoAccess |
                                       valhalla::baldr::kMotorcycleAccess)))
          continue;
        auto geom=tile->edgeinfo(edge).shape();
        if (geom.size()<2) continue;
        if (!edge->forward()) std::reverse(geom.begin(),geom.end());
        ++shapes;
        for (std::size_t j=1;j<geom.size();++j) {
          const auto& a=geom[j-1];
          const auto& b=geom[j];
          const double low=std::min(a.lat(),b.lat())-lat_pad;
          const double high=std::max(a.lat(),b.lat())+lat_pad;
          auto first=std::lower_bound(q.begin(),q.end(),low,
              [](const Query& x,double y){return x.lat<y;});
          auto last=std::upper_bound(first,q.end(),high,
              [](double y,const Query& x){return y<x.lat;});
          ++segments;
          for (auto it=first;it!=last;++it) {
            const double lon_pad=(radius+1.0) /
                (kMetresPerDegree*std::max(.1,std::cos(it->lat*kPi/180.0)));
            if (it->lon < std::min(a.lng(),b.lng())-lon_pad ||
                it->lon > std::max(a.lng(),b.lng())+lon_pad)
              continue;
            const double distance=metres_to_segment(*it,a,b);
            if (distance>radius) continue;
            const auto key=std::make_pair(it->id,id.value);
            const auto found=matches.find(key);
            if (found==matches.end() || distance<found->second)
              matches[key]=distance;
          }
        }
      }
    }
    if (scanned!=all.size())
      throw std::runtime_error("Original receiver tile inventory not fully scanned");
    // Only emit AFTER every tile was successfully read; no partial-success JSON.
    std::cout << std::setprecision(11)
      << "{\"schema\":\"roadpilot.f8-original-native-all-receiver-directed-shapes\","
         "\"version\":1,\"valhallaVersion\":\"" << ROADPILOT_VALHALLA_VERSION
      << "\",\"allGraphReaderTilesExhaustivelyRead\":true,"
      << "\"sourcePointCount\":" << q.size()
      << ",\"originalReceiverTileCount\":" << scanned
      << ",\"allDirectedEdgesVisited\":" << directed
      << ",\"originalRoutableRoadShapesRead\":" << shapes
      << ",\"originalRoutableSegmentsRead\":" << segments
      << ",\"nearbyOriginalDirectedShapes\":[";
    bool first=true;
    for (const auto& [k,d]:matches) {
      if (!first) std::cout << ',';
      first=false;
      std::cout << "{\"sourceGraphId\":" << k.first
                << ",\"receiverGraphId\":" << k.second
                << ",\"nativeSourceDistanceMetres\":" << d << '}';
    }
    std::cout << "],\"candidatePairs\":" << matches.size() << "}\n";
    if (!std::cout) throw std::runtime_error("Original receiver native scan output write failed");
    return 0;
  } catch (const std::exception& ex) {
    std::cerr << "native_f8_full_receiver_nearpoint failed: " << ex.what()
              << "\nPARTIAL_OUTPUT_INVALID\n";
    return 2;
  }
}
