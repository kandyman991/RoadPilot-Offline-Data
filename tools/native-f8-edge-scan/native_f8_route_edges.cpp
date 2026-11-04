// Original Valhalla 3.6.3 native Trip protobuf route-edge identity extractor.
// Not a shape replay or trace_attributes request. Read-only; each run routes
// only inside ONE immutable graph and returns the original TripLeg::Node::Edge ids.
#include <valhalla/proto/api.pb.h>
#include <valhalla/tyr/actor.h>
#include <valhalla/midgard/logging.h>
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef ROADPILOT_VALHALLA_VERSION
#error Configure with pinned libvalhalla version
#endif

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--version") {
    std::cout << ROADPILOT_VALHALLA_VERSION << '\n';
    return 0;
  }
  if (argc != 2) {
    std::cerr << "usage: native_f8_route_edges <exact-valhalla-config> < route_request.json\n";
    return 64;
  }
  try {
    valhalla::midgard::logging::Configure({{"type", "std_err"}, {"color", "false"}});
    const std::string req((std::istreambuf_iterator<char>(std::cin)),
                          std::istreambuf_iterator<char>());
    if (req.empty() || req.size() > 32768)
      throw std::runtime_error("Native route request is empty or exceeds 32 KiB");
    boost::property_tree::ptree config;
    boost::property_tree::read_json(argv[1], config);
    valhalla::tyr::actor_t actor(config, true);
    valhalla::Api api;
    // Crucial: request native route calculation ONCE, capture the SAME
    // original protobuf object. Never infer directed GraphIds by independently
    // correlating the encoded route shape with trace_attributes(edge_walk).
    const auto serialized_route = actor.route(req, nullptr, &api);
    if (serialized_route.empty())
      throw std::runtime_error("Original route produced empty serialized output");
    if (api.trip().routes_size() != 1)
      throw std::runtime_error("Expected exactly one original TripRoute");
    const auto& route = api.trip().routes(0);
    if (route.legs_size() != 1)
      throw std::runtime_error("Expected exactly one graph-local original TripLeg");
    const auto& leg = route.legs(0);
    if (leg.node_size() < 2)
      throw std::runtime_error("Original TripLeg contains fewer than 2 native nodes");
    std::vector<std::pair<uint64_t, uint64_t>> edge_ids;
    edge_ids.reserve(leg.node_size());
    for (const auto& node : leg.node()) {
      if (!node.has_edge()) continue;
      const auto& edge = node.edge();
      if (edge.id() == 0 || edge.way_id() == 0)
        throw std::runtime_error("Original TripLeg has missing directed GraphId/wayId");
      edge_ids.emplace_back(edge.id(), edge.way_id());
    }
    if (edge_ids.empty())
      throw std::runtime_error("Original TripLeg contains no native routed edge IDs");
    // TripLeg::summary is not populated by this Valhalla action. Odin
    // serializes actual metrics into trip.summary in the SAME route return.
    // Do not mistake protobuf defaults (0,0) for valid route costs.
    boost::property_tree::ptree route_json;
    std::istringstream serialized(serialized_route);
    boost::property_tree::read_json(serialized, route_json);
    const double seconds = route_json.get<double>("trip.summary.time");
    const double km = route_json.get<double>("trip.summary.length");
    if (!std::isfinite(seconds) || seconds <= 0
        || !std::isfinite(km) || km <= 0)
      throw std::runtime_error("Original route has invalid serialized route metrics");
    std::cout << std::setprecision(12)
              << "{\"schema\":\"roadpilot.f8-original-valhalla-route-edges\","
              << "\"version\":1,\"valhallaVersion\":\"" << ROADPILOT_VALHALLA_VERSION
              << "\",\"edgeIdOrigin\":\"ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF\","
              << "\"routeCalculationCount\":1,\"graphLocalOnly\":true,"
              << "\"legCount\":1,\"nodeCount\":" << leg.node_size()
              << ",\"durationSeconds\":" << seconds
              << ",\"distanceKm\":" << km
              << ",\"encodedShape\":" << std::quoted(leg.shape())
              << ",\"directedEdges\":[";
    bool first = true;
    for (const auto& [id, way] : edge_ids) {
      if (!first) std::cout << ',';
      first = false;
      std::cout << "{\"graphId\":" << id << ",\"wayId\":" << way << '}';
    }
    std::cout << "],\"firstDirectedGraphId\":" << edge_ids.front().first
              << ",\"lastDirectedGraphId\":" << edge_ids.back().first
              << ",\"routeEdgeIdentity\":\"ORIGINAL_VALHALLA_ROUTE_PROTOBUF\","
              << "\"crossGraphLegalTransfer\":\"NOT_VERIFIED\","
              << "\"physicalRoadFinalEdge\":\"NOT_VERIFIED\","
              << "\"productionPublication\":\"BLOCKED\"}\n";
    if (!std::cout)
      throw std::runtime_error("Native route evidence output stream failed");
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "native_f8_route_edges failed: " << e.what()
              << "\nPARTIAL_STDOUT_MUST_BE_DISCARDED\n";
    return 2;
  }
}
