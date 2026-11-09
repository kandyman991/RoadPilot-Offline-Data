// Region-independent original Valhalla boundary terminal extractor.
// This tool reads ONLY the tile IDs selected from a region's own 25km buffer
// outline by extract_f8_region_final_edges.py; it does not walk all graph tiles,
// route with Valhalla, or infer receiving-graph identities.
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/baldr/graphconstants.h>
#include <valhalla/midgard/logging.h>
#include <valhalla/sif/autocost.h>
#include <valhalla/sif/motorcyclecost.h>
#include <valhalla/sif/edgelabel.h>
#include <valhalla/sif/costconstants.h>
#include <valhalla/proto/options.pb.h>
#include "original_buffer_cut.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <vector>
#include <fstream>
#include <iomanip>
#include <memory>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_set>

#ifndef ROADPILOT_VALHALLA_VERSION
#error Build against the exact libvalhalla version used for the graph.
#endif

namespace {
namespace baldr = valhalla::baldr;
constexpr uint32_t kModes = baldr::kAutoAccess | baldr::kMotorcycleAccess;

uint64_t decimal_id(const std::string& line) {
  if (line.empty() || line.find_first_not_of("0123456789") != std::string::npos)
    throw std::runtime_error("Tile input must contain unsigned decimal GraphIds");
  return std::stoull(line);
}

// A targeted continuation view for source edges at the cutoff. This is the
// SAME original GraphReader source stage, not a second routing/discovery
// pipeline: only each supplied edge and its immediate native incident and
// hierarchy-transition edges are read. No OSM/road-name equivalence.
void print_directed_edge(valhalla::baldr::GraphReader& reader,
                         const baldr::GraphId& id) {
  const auto tile = reader.GetGraphTile(id);
  if (!tile || id.id() >= tile->header()->directededgecount())
    throw std::runtime_error("Missing original directed edge for local continuation");
  const auto* edge = tile->directededge(id);
  const auto end_id = edge->endnode();
  const auto end_tile = reader.GetGraphTile(end_id);
  if (!end_tile || end_id.id() >= end_tile->header()->nodecount())
    throw std::runtime_error("Missing original end node for local continuation");
  auto shape = tile->edgeinfo(edge).shape();
  if (!edge->forward()) std::reverse(shape.begin(), shape.end());
  if (shape.empty()) throw std::runtime_error("Missing original directed edge shape");
  const auto& end = shape.back();
  const auto& start = shape.front();
  if (!std::isfinite(end.lat()) || !std::isfinite(end.lng()) ||
      !std::isfinite(start.lat()) || !std::isfinite(start.lng()))
    throw std::runtime_error("Nonfinite original road shape");
  std::cout << "{\"graphId\":" << id.value << ",\"access\":"
            << (edge->forwardaccess() & kModes)
            << ",\"endNodeGraphId\":" << end_id.value
            << ",\"startLat\":" << start.lat()
            << ",\"startLon\":" << start.lng()
            << ",\"endLat\":" << end_tile->get_node_ll(end_id).lat()
            << ",\"endLon\":" << end_tile->get_node_ll(end_id).lng()
            << ",\"roadClass\":" << static_cast<uint32_t>(edge->classification())
            << ",\"roadUse\":" << static_cast<uint32_t>(edge->use())
            << ",\"layer\":" << static_cast<int>(tile->edgeinfo(edge).layer())
            << ",\"bridge\":" << (edge->bridge() ? "true" : "false")
            << ",\"tunnel\":" << (edge->tunnel() ? "true" : "false")
            << ",\"shortcut\":" << (edge->is_shortcut() ? "true" : "false")
            << ",\"transit\":" << (edge->IsTransitLine() ? "true" : "false")
            << ",\"approach\":";
  // Last distinct vertex points into X. The corresponding first distinct
  // vertex points *out* of the node for a candidate continuation.
  bool found = false;
  for (std::size_t i = shape.size() - 1; i > 0; --i) {
    const auto& prior = shape[i - 1];
    if (!std::isfinite(prior.lat()) || !std::isfinite(prior.lng()))
      throw std::runtime_error("Nonfinite original approach vertex");
    if (std::abs(prior.lat() - end.lat()) > 1e-8 ||
        std::abs(prior.lng() - end.lng()) > 1e-8) {
      std::cout << '[' << prior.lat() << ',' << prior.lng() << ']';
      found = true; break;
    }
  }
  if (!found) std::cout << "null";
  std::cout << ",\"departure\":";
  found = false;
  for (std::size_t i = 1; i < shape.size(); ++i) {
    const auto& next = shape[i];
    if (!std::isfinite(next.lat()) || !std::isfinite(next.lng()))
      throw std::runtime_error("Nonfinite original departure vertex");
    if (std::abs(next.lat() - start.lat()) > 1e-8 ||
        std::abs(next.lng() - start.lng()) > 1e-8) {
      std::cout << '[' << next.lat() << ',' << next.lng() << ']';
      found = true; break;
    }
  }
  if (!found) std::cout << "null";
  std::cout << '}';
}

// Evaluate exactly one native transition using Valhalla 3.6.3's OWN
// AutoCost/MotorcycleCost Allowed() rules, never a shortest-route search.
// Without a full historical route, date/time, or hierarchy traversal state,
// do not invent an ALLOWED verdict for complex/conditional cases.
std::string one_step_costing_status(const valhalla::sif::DynamicCost& costing,
                                   uint32_t mode, const baldr::GraphId& source_id,
                                   const baldr::DirectedEdge* source_edge,
                                   const baldr::GraphId& next_id,
                                   const baldr::DirectedEdge* next,
                                   const baldr::graph_tile_ptr& next_tile,
                                   bool via_hierarchy) {
  if (!(source_edge->forwardaccess() & mode) || !(next->forwardaccess() & mode))
    return "NO_MODE_ACCESS";
  if (source_edge->is_shortcut() || next->is_shortcut())
    return "UNRESOLVED_SHORTCUT";
  if (via_hierarchy)
    return "UNRESOLVED_HIERARCHY_CONTEXT";
  if (source_edge->part_of_complex_restriction() ||
      source_edge->start_restriction() || source_edge->end_restriction() ||
      next->part_of_complex_restriction() || next->start_restriction() ||
      next->end_restriction() || (next->access_restriction() & mode) ||
      (source_edge->access_restriction() & mode) ||
      source_edge->destonly() || next->destonly())
    return "UNRESOLVED_PATH_OR_TIME_CONTEXT";
  // Only the immediately preceding ORIGINAL directed source edge exists in
  // this bounded query. A true route search could have path-dependent flags.
  valhalla::sif::EdgeLabel pred(baldr::kInvalidLabel, source_id,
       source_edge, valhalla::sif::Cost(0.0f, 0.0f), 0.0f,
       costing.travel_mode(), 0, 255, false,
       false, valhalla::sif::InternalTurn::kNoTurn);
  uint8_t restriction_idx = 255;
  uint8_t destonly_mask = 0;
  const bool allowed = costing.Allowed(next, false, pred, next_tile, next_id,
                                       0, 0, restriction_idx, destonly_mask);
  return allowed ? "ALLOWED_NATIVE_IMMEDIATE" : "DENIED_NATIVE_IMMEDIATE";
}

int inspect_local_continuations(int argc, char** argv) {
  if (argc != 4 && argc != 5)
    throw std::runtime_error("usage: --local-continuations <valhalla.json> <original_directed_ids.txt> [--evaluate-native-costing]");
  const bool evaluate_costing = argc == 5;
  if (evaluate_costing && std::string(argv[4]) != "--evaluate-native-costing")
    throw std::runtime_error("Unknown local costing inspection option");
  valhalla::Costing auto_options;
  auto_options.set_type(valhalla::Costing::auto_);
  valhalla::Costing motorcycle_options;
  motorcycle_options.set_type(valhalla::Costing::motorcycle);
  const auto auto_cost = evaluate_costing ?
      valhalla::sif::CreateAutoCost(auto_options) : nullptr;
  const auto motorcycle_cost = evaluate_costing ?
      valhalla::sif::CreateMotorcycleCost(motorcycle_options) : nullptr;
  boost::property_tree::ptree config;
  boost::property_tree::read_json(argv[2], config);
  baldr::GraphReader reader(config.get_child("mjolnir"));
  std::ifstream source(argv[3]);
  if (!source) throw std::runtime_error("Cannot open source directed edge IDs");
  std::unordered_set<uint64_t> visited;
  uint64_t inspected = 0;
  std::cout << std::setprecision(12);
  std::string line;
  while (std::getline(source, line)) {
    const baldr::GraphId input(decimal_id(line));
    if (!input.is_valid() || !visited.insert(input.value).second)
      throw std::runtime_error("Invalid or duplicate original source directed ID");
    const auto tile = reader.GetGraphTile(input);
    if (!tile || input.id() >= tile->header()->directededgecount())
      throw std::runtime_error("Missing original source directed ID");
    const auto* edge = tile->directededge(input);
    if (edge->IsTransitLine() || edge->is_shortcut() || !(edge->forwardaccess() & kModes))
      throw std::runtime_error("Selected source is not eligible original directed road");
    std::cout << "{\"kind\":\"local-continuations\",\"source\":";
    print_directed_edge(reader, input);
    std::cout << ",\"options\":[";
    const auto end_id = edge->endnode();
    std::deque<baldr::GraphId> pending{end_id};
    std::unordered_set<uint64_t> seen_nodes{end_id.value};
    std::unordered_set<uint64_t> seen_options;
    bool first = true;
    while (!pending.empty()) {
      const auto local = pending.front(); pending.pop_front();
      const auto local_tile = reader.GetGraphTile(local);
      if (!local_tile || local.id() >= local_tile->header()->nodecount())
        throw std::runtime_error("Missing native hierarchy peer node");
      const auto* node = local_tile->node(local);
      for (uint32_t j = 0; j < node->edge_count(); ++j) {
        if (local == end_id && j == edge->opp_index()) continue;
        const baldr::GraphId out(local.tileid(), local.level(), node->edge_index() + j);
        const auto* candidate = local_tile->directededge(out);
        if ((candidate->forwardaccess() & kModes) == 0 || candidate->IsTransitLine())
          continue;
        if (!seen_options.insert(out.value).second) continue;
        if (!first) std::cout << ',';
        first = false;
        std::cout << "{\"viaHierarchy\":" << (local == end_id ? "false" : "true")
                  << ",\"fromNodeGraphId\":" << local.value
                  << ",\"edge\":";
        print_directed_edge(reader, out);
        if (evaluate_costing) {
          std::cout << ",\"nativeImmediateCosting\":{";
          std::cout << "\"car\":\""
                    << one_step_costing_status(*auto_cost, baldr::kAutoAccess,
                         input, edge, out, candidate, local_tile, local != end_id)
                    << "\",\"motorcycle\":\""
                    << one_step_costing_status(*motorcycle_cost,
                         baldr::kMotorcycleAccess, input, edge, out,
                         candidate, local_tile, local != end_id)
                    << "\"}";
        }
        std::cout << '}';
      }
      for (const auto& transition : local_tile->GetNodeTransitions(local)) {
        const auto peer = transition.endnode();
        if (!peer.is_valid()) throw std::runtime_error("Bad original hierarchy transition");
        if (seen_nodes.insert(peer.value).second) pending.push_back(peer);
      }
      if (seen_nodes.size() > 32)
        throw std::runtime_error("Original hierarchy fanout unexpectedly large");
    }
    std::cout << "]}\n";
    ++inspected;
  }
  if (!source.eof() || inspected == 0) throw std::runtime_error("No complete original input edge ID set");
  std::cout << "{\"kind\":\"complete\",\"edgesInspected\":" << inspected
            << ",\"valhallaVersion\":\"" << ROADPILOT_VALHALLA_VERSION << "\"}\n";
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--protocol") {
    std::cout << "roadpilot.f8-native-source-7\n";
    return 0;
  }
  if (argc == 2 && std::string(argv[1]) == "--version") {
    std::cout << ROADPILOT_VALHALLA_VERSION << '\n';
    return 0;
  }
  if (argc > 1 && std::string(argv[1]) == "--local-continuations") {
    try {
      valhalla::midgard::logging::Configure({{"type", "std_err"}, {"color", "false"}});
      return inspect_local_continuations(argc, argv);
    } catch (const std::exception& e) {
      std::cerr << "local_continuations: " << e.what() << "\nPARTIAL_OUTPUT_NOT_VALID\n";
      return 2;
    }
  }
  if (argc != 3 && argc != 4 && argc != 5) {
    std::cerr << "usage: native_f8_boundary_final_edges <valhalla.json> <tile_ids.txt> [original-25km-buffer.geojson [derived-shared-cut.geojson]]\n";
    return 64;
  }
  try {
    valhalla::midgard::logging::Configure({{"type", "std_err"}, {"color", "false"}});
    boost::property_tree::ptree config;
    boost::property_tree::read_json(argv[1], config);
    baldr::GraphReader reader(config.get_child("mjolnir"));
    const bool cut_only = argc >= 4;
    const bool pair_only = argc == 5;
    std::unique_ptr<roadpilot_cut::OriginalCut> original_cut;
    if (cut_only) original_cut = std::make_unique<roadpilot_cut::OriginalCut>(
        argv[3], pair_only ? argv[4] : "");
    std::ifstream source(argv[2]);
    if (!source) throw std::runtime_error("Cannot open selected boundary tile IDs");

    std::unordered_set<uint64_t> visited_tiles;
    uint64_t directed_examined = 0, edges_emitted = 0;
    std::cout << std::setprecision(12);
    std::string line;
    while (std::getline(source, line)) {
      const baldr::GraphId tile_id(decimal_id(line));
      if (!tile_id.is_valid() || tile_id.id() != 0)
        throw std::runtime_error("Expected a graph TILE GraphId with index zero");
      if (!visited_tiles.insert(tile_id.value).second)
        throw std::runtime_error("Duplicate selected tile");
      const auto tile = reader.GetGraphTile(tile_id);
      if (!tile) throw std::runtime_error("Missing selected original graph tile");
      for (uint32_t n = 0; n < tile->header()->nodecount(); ++n) {
        const baldr::GraphId node_id(tile_id.tileid(), tile_id.level(), n);
        const auto start = tile->get_node_ll(node_id);
        const auto* node = tile->node(n);
        for (uint32_t offset = 0; offset < node->edge_count(); ++offset) {
          const baldr::GraphId edge_id(tile_id.tileid(), tile_id.level(),
                                       node->edge_index() + offset);
          const auto* edge = tile->directededge(edge_id);
          ++directed_examined;
          if (edge->IsTransitLine() || edge->is_shortcut() ||
              (edge->forwardaccess() & kModes) == 0)
            continue;
          const auto end_id = edge->endnode();
          const auto end_tile = reader.GetGraphTile(end_id);
          if (!end_tile || end_id.id() >= end_tile->header()->nodecount())
            throw std::runtime_error("Broken native directed end-node reference");
          const auto end = end_tile->get_node_ll(end_id);
          // An endpoint alone cannot identify the same physical directed
          // road in the receiver. Record the last distinct point of the
          // ORIGINAL edge shape as an approach tangent to X. Never invent a
          // second handoff or select a receiving edge by GPS distance alone.
          auto directed_shape = tile->edgeinfo(edge).shape();
          if (!edge->forward())
            std::reverse(directed_shape.begin(), directed_shape.end());
          if (cut_only && !original_cut->intersects(directed_shape)) continue;
          const std::string cut_orientation = cut_only ? original_cut->direction(directed_shape) : "NOT_FILTERED";
          bool has_approach = false;
          double approach_lat = 0.0, approach_lon = 0.0;
          if (!directed_shape.empty()) {
            const auto& x = directed_shape.back();
            if (!std::isfinite(x.lat()) || !std::isfinite(x.lng()))
              throw std::runtime_error("Invalid native directed geometry endpoint");
            for (std::size_t i = directed_shape.size() - 1; i > 0; --i) {
              const auto& previous = directed_shape[i - 1];
              if (!std::isfinite(previous.lat()) || !std::isfinite(previous.lng()))
                throw std::runtime_error("Invalid native directed geometry vertex");
              if (std::abs(previous.lat() - x.lat()) > 1e-8 ||
                  std::abs(previous.lng() - x.lng()) > 1e-8) {
                has_approach = true;
                approach_lat = previous.lat();
                approach_lon = previous.lng();
                break;
              }
            }
          }
          const auto* end_node = end_tile->node(end_id);
          if (edge->opp_index() >= end_node->edge_count())
            throw std::runtime_error("Broken opposing edge index");

          // A terminal is not just "no more edges on the current hierarchy
          // level". Valhalla may expose a continuation through an immediate
          // zero-length hierarchy transition. Visit only transition-linked
          // versions of THIS end node; never traverse the wider road graph.
          // Count shortcuts as possible continuations (not candidate finals).
          uint32_t other_modes = 0;
          std::deque<baldr::GraphId> pending{end_id};
          std::unordered_set<uint64_t> seen_nodes;
          seen_nodes.insert(end_id.value);
          while (!pending.empty()) {
            const auto local_id = pending.front();
            pending.pop_front();
            const auto local_tile = reader.GetGraphTile(local_id);
            if (!local_tile || local_id.id() >= local_tile->header()->nodecount())
              throw std::runtime_error("Missing native transition-linked end node");
            const auto* local_node = local_tile->node(local_id);
            for (uint32_t j = 0; j < local_node->edge_count(); ++j) {
              // Only the exact reverse on the original hierarchy is known
              // to be the opposing directed edge. Other peer-level edges
              // must remain unresolved until road correlation, not discarded.
              if (local_id == end_id && j == edge->opp_index()) continue;
              const baldr::GraphId out_id(local_id.tileid(), local_id.level(),
                                          local_node->edge_index() + j);
              const auto* next = local_tile->directededge(out_id);
              if (!next->IsTransitLine())
                other_modes |= (next->forwardaccess() & kModes);
            }
            for (const auto& transition : local_tile->GetNodeTransitions(local_id)) {
              const auto peer = transition.endnode();
              if (!peer.is_valid())
                throw std::runtime_error("Invalid original hierarchy transition");
              if (seen_nodes.insert(peer.value).second)
                pending.push_back(peer);
            }
          }
          // A graph-local terminal candidate remains a candidate, NOT a
          // confirmed last physical-road edge. Receiving correlation is later.
          const uint32_t terminal_modes = edge->forwardaccess() & kModes & ~other_modes;
          // Output only edges with at least one definitively mode-terminal
          // local end, OR an unresolved local continuation. The receiving
          // correlator will determine whether an actual counterpart exists.
          std::cout << "{\"kind\":\"edge\","
                    << "\"graphId\":" << edge_id.value
                    << ",\"sourceNodeGraphId\":" << node_id.value
                    << ",\"endNodeGraphId\":" << end_id.value
                    << ",\"startLat\":" << start.lat()
                    << ",\"startLon\":" << start.lng()
                    << ",\"endLat\":" << end.lat()
                    << ",\"endLon\":" << end.lng()
                    << ",\"directedShapeForward\":" << (edge->forward() ? "true" : "false")
                    << ",\"hasNativeApproachTangent\":" << (has_approach ? "true" : "false")
                    << ",\"approachLat\":";
          if (has_approach) std::cout << approach_lat;
          else std::cout << "null";
          std::cout << ",\"approachLon\":";
          if (has_approach) std::cout << approach_lon;
          else std::cout << "null";
          std::cout
                    << ",\"roadUse\":" << static_cast<uint32_t>(edge->use())
                    << ",\"originalCutOrientation\":\"" << cut_orientation << "\""
                    << ",\"access\":" << (edge->forwardaccess() & kModes)
                    << ",\"nativeTerminalModes\":" << terminal_modes
                    << ",\"localContinuingModes\":" << other_modes
                    << ",\"deadend\":" << (edge->deadend() ? "true" : "false")
                    << ",\"isRoad\":" << (edge->is_road() ? "true" : "false")
                    << ",\"roadClass\":" << static_cast<uint32_t>(edge->classification())
                    << ",\"bridge\":" << (edge->bridge() ? "true" : "false")
                    << ",\"tunnel\":" << (edge->tunnel() ? "true" : "false")
                    << ",\"layer\":" << static_cast<int>(tile->edgeinfo(edge).layer())
                    << "}\n";
          ++edges_emitted;
        }
      }
    }
    if (!source.eof()) throw std::runtime_error("Failed to read selected boundary tiles");
    if (visited_tiles.empty()) throw std::runtime_error("No original boundary tiles provided");
    std::cout << "{\"kind\":\"complete\",\"valhallaVersion\":\""
              << ROADPILOT_VALHALLA_VERSION
              << "\",\"selectedTiles\":" << visited_tiles.size()
              << ",\"directedExamined\":" << directed_examined
              << ",\"edgesEmitted\":" << edges_emitted
              << ",\"originalCutFilterApplied\":" << (cut_only ? "true" : "false")
              << ",\"sharedCutFilterApplied\":" << (pair_only ? "true" : "false")
              << "}\n";
    if (!std::cout) throw std::runtime_error("Failed writing native boundary records");
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "native_f8_boundary_final_edges: " << e.what()
              << "\nPARTIAL_OUTPUT_NOT_VALID\n";
    return 2;
  }
}
