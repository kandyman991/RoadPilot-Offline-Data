// Read-only exact directed endpoint extractor for F8 terminal research.
// NOT a handoff producer: the deadend flag does not establish cross-graph
// continuity, and graph-local GraphIds are never compared across graphs.
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/baldr/graphconstants.h>
#include <valhalla/midgard/logging.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <deque>
#include <utility>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_set>

#ifndef ROADPILOT_VALHALLA_VERSION
#error Build with the Valhalla version supplied by CMake.
#endif

namespace {
uint64_t graph_id_from_line(const std::string& text) {
  if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos)
    throw std::invalid_argument("Input requires one unsigned decimal directed GraphId per line");
  size_t used = 0;
  const auto value = std::stoull(text, &used);
  if (used != text.size())
    throw std::invalid_argument("Invalid GraphId integer");
  return value;
}
}  // namespace

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--version") {
    std::cout << ROADPILOT_VALHALLA_VERSION << '\n';
    return 0;
  }
  const bool include_lineage = argc == 4 && std::string(argv[3]) == "--lineage";
  const bool include_continuations =
      (argc == 4 && std::string(argv[3]) == "--continuations") || include_lineage;
  const bool include_geometry = argc == 4 && std::string(argv[3]) == "--geometry";
  if (argc != 3 && !include_continuations && !include_geometry) {
    std::cerr << "usage: native_f8_directed_endpoints <valhalla.json> <graph_ids.txt> [--continuations|--geometry|--lineage]\n";
    return 64;
  }
  try {
    valhalla::midgard::logging::Configure({{"type", "std_err"}, {"color", "false"}});
    boost::property_tree::ptree cfg;
    boost::property_tree::read_json(argv[1], cfg);
    valhalla::baldr::GraphReader reader(cfg.get_child("mjolnir"));
    std::ifstream input(argv[2]);
    if (!input.is_open()) throw std::runtime_error("Cannot read directed GraphId input");

    std::unordered_set<uint64_t> seen;
    std::string line;
    std::size_t row = 0;
    std::cout << std::setprecision(11);
    while (std::getline(input, line)) {
      ++row;
      const uint64_t value = graph_id_from_line(line);
      if (!seen.insert(value).second)
        throw std::runtime_error("Repeated directed GraphId in input");
      const valhalla::baldr::GraphId id(value);
      if (!id.is_valid()) throw std::runtime_error("Invalid directed GraphId");

      const auto tile = reader.GetGraphTile(id);
      if (!tile || id.id() >= tile->header()->directededgecount())
        throw std::runtime_error("Directed edge is absent from graph archive");
      const auto* edge = tile->directededge(id);
      const auto end_id = edge->endnode();
      const auto end_tile = reader.GetGraphTile(end_id);
      if (!end_tile || end_id.id() >= end_tile->header()->nodecount())
        throw std::runtime_error("Directed edge end node is missing from graph archive");
      const auto end = end_tile->get_node_ll(end_id);
      const auto way = tile->edgeinfo(edge).wayid();
      std::cout << "{\"sourceGraphId\":" << value
                << ",\"endNodeGraphId\":" << end_id.value
                << ",\"endLat\":" << end.lat()
                << ",\"endLon\":" << end.lng()
                << ",\"deadend\":" << (edge->deadend() ? "true" : "false")
                << ",\"notThru\":" << (edge->not_thru() ? "true" : "false")
                << ",\"forward\":" << (edge->forward() ? "true" : "false")
                << ",\"wayId\":" << way
                << ",\"forwardAccess\":" << edge->forwardaccess()
                << ",\"reverseAccess\":" << edge->reverseaccess();
      if (include_geometry) {
        // Full directed Valhalla 3.6.3 shape, NOT a physical cross-graph proof.
        // Keep the original graph-local node subdivision; never infer peer
        // GraphIds or silently snap endpoints in the extractor.
        auto shape = tile->edgeinfo(edge).shape();
        if (!edge->forward()) std::reverse(shape.begin(), shape.end());
        if (shape.size() < 2)
          throw std::runtime_error("Missing native directed road geometry");
        std::cout << ",\"directedGeometry\":[";
        for (std::size_t i = 0; i < shape.size(); ++i) {
          const auto& point = shape[i];
          if (!std::isfinite(point.lat()) || !std::isfinite(point.lng()) ||
              std::abs(point.lat()) > 90 || std::abs(point.lng()) > 180)
            throw std::runtime_error("Invalid native directed geometry point");
          if (i) std::cout << ',';
          std::cout << '[' << point.lat() << ',' << point.lng() << ']';
        }
        std::cout << ']';
      }
      if (include_continuations) {
        // Exact receiving graph node adjacency, NOT turn/mode route proof.
        const auto* node = end_tile->node(end_id.id());
        // Opposing directed edge is the immediate reverse of the incoming edge.
        // Exclude it only from diagnostic forward-continuation counts, never
        // from underlying evidence; route costs and turn legality still need Valhalla.
        if (edge->opp_index() >= node->edge_count())
          throw std::runtime_error("Invalid opposing directed edge index");
        const valhalla::baldr::GraphId reverse(
            end_tile->id().tileid(), end_tile->id().level(),
            node->edge_index() + edge->opp_index());
        std::cout << ",\"opposingGraphId\":" << reverse.value;
        std::cout << ",\"nativeOutgoingDegree\":" << node->edge_count();
        std::cout << ",\"outgoingDirectedEdges\":[";
        for (uint32_t offset = 0; offset < node->edge_count(); ++offset) {
          const valhalla::baldr::GraphId other(
              end_tile->id().tileid(), end_tile->id().level(),
              node->edge_index() + offset);
          const auto* next = end_tile->directededge(other);
          if (offset) std::cout << ',';
          const uint32_t mask = next->forwardaccess();
          std::cout << "{\"graphId\":" << other.value
                    << ",\"endNodeGraphId\":" << next->endnode().value
                    << ",\"forwardAccess\":" << mask
                    << ",\"isRoad\":" << (next->is_road() ? "true" : "false")
                    << ",\"isShortcut\":" << (next->is_shortcut() ? "true" : "false")
                    << ",\"motorcycleBit\":" <<
                       ((mask & valhalla::baldr::kMotorcycleAccess) != 0 ? "true" : "false")
                    << ",\"autoBit\":" <<
                       ((mask & valhalla::baldr::kAutoAccess) != 0 ? "true" : "false")
                    << '}';
        }
        std::cout << ']';
      }
      if (include_lineage) {
        // Native GraphReader hierarchy transitions are ZERO-LENGTH moves
        // between levels at the SAME physical intersection. An original
        // TripLeg may use a successor edge on another level; auditing only
        // node->edge_count() would falsely declare that route disconnected.
        // Expose every transition and every directed branch, including
        // opposing reverse, shortcuts, nonroad and mode-inaccessible edges.
        std::deque<std::pair<valhalla::baldr::GraphId, unsigned>> nodes;
        std::unordered_set<uint64_t> visited;
        nodes.emplace_back(end_id, 0);
        visited.insert(end_id.value);
        std::cout << ",\"nativeAllHierarchyContinuationNodes\":[";
        bool first_node = true;
        while (!nodes.empty()) {
          const auto [node_id, depth] = nodes.front();
          nodes.pop_front();
          if (depth > 4 || visited.size() > 32)
            throw std::runtime_error("Unexpected cyclic/oversized native hierarchy transition fanout");
          const auto node_tile = reader.GetGraphTile(node_id);
          if (!node_tile || node_id.id() >= node_tile->header()->nodecount())
            throw std::runtime_error("Hierarchy transition node missing from immutable graph");
          const auto* info = node_tile->node(node_id.id());
          const auto position = node_tile->get_node_ll(node_id);
          if (!std::isfinite(position.lat()) || !std::isfinite(position.lng()))
            throw std::runtime_error("Nonfinite original hierarchy node position");
          if (!first_node) std::cout << ',';
          first_node = false;
          std::cout << "{\"nodeGraphId\":" << node_id.value
                    << ",\"transitionDepth\":" << depth
                    << ",\"nodeLat\":" << position.lat()
                    << ",\"nodeLon\":" << position.lng()
                    << ",\"allOutgoingDirectedEdges\":[";
          for (uint32_t n = 0; n < info->edge_count(); ++n) {
            const valhalla::baldr::GraphId out_id(node_id.tileid(), node_id.level(),
                                                  info->edge_index() + n);
            const auto* out = node_tile->directededge(out_id);
            if (n) std::cout << ',';
            std::cout << "{\"graphId\":" << out_id.value
                      << ",\"endNodeGraphId\":" << out->endnode().value
                      << ",\"forwardAccess\":" << out->forwardaccess()
                      << ",\"isRoad\":" << (out->is_road() ? "true" : "false")
                      << ",\"isShortcut\":" << (out->is_shortcut() ? "true" : "false")
                      << "}";
          }
          std::cout << "],\"nativeHierarchyTransitions\":[";
          bool first_transition = true;
          for (const auto& transition : node_tile->GetNodeTransitions(node_id)) {
            if (!first_transition) std::cout << ',';
            first_transition = false;
            const auto peer = transition.endnode();
            if (!peer.is_valid())
              throw std::runtime_error("Invalid native hierarchy transition GraphId");
            std::cout << "{\"nodeGraphId\":" << peer.value
                      << ",\"up\":" << (transition.up() ? "true" : "false") << "}";
            if (visited.insert(peer.value).second)
              nodes.emplace_back(peer, depth + 1);
          }
          std::cout << "]}";
        }
        std::cout << "]";
      }
      std::cout << "}\n";
      if (!std::cout) throw std::runtime_error("Endpoint output write failed");
    }
    if (!input.eof()) throw std::runtime_error("Endpoint input read failed");
    if (row == 0) throw std::runtime_error("Empty directed GraphId inventory");
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "native_f8_directed_endpoints failed: " << error.what()
              << "\nPARTIAL_STDOUT_MUST_BE_DISCARDED\n";
    return 2;
  }
}
