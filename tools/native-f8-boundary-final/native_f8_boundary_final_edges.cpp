// Region-independent original Valhalla boundary terminal extractor.
// This tool reads ONLY the tile IDs selected from a region's own 25km buffer
// outline by extract_f8_region_final_edges.py; it does not walk all graph tiles,
// route with Valhalla, or infer receiving-graph identities.
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/baldr/graphconstants.h>
#include <valhalla/midgard/logging.h>

#include <algorithm>
#include <cstdint>
#include <deque>
#include <fstream>
#include <iomanip>
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
}  // namespace

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--version") {
    std::cout << ROADPILOT_VALHALLA_VERSION << '\n';
    return 0;
  }
  if (argc != 3) {
    std::cerr << "usage: native_f8_boundary_final_edges <valhalla.json> <tile_ids.txt>\n";
    return 64;
  }
  try {
    valhalla::midgard::logging::Configure({{"type", "std_err"}, {"color", "false"}});
    boost::property_tree::ptree config;
    boost::property_tree::read_json(argv[1], config);
    baldr::GraphReader reader(config.get_child("mjolnir"));
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
              << ",\"edgesEmitted\":" << edges_emitted << "}\n";
    if (!std::cout) throw std::runtime_error("Failed writing native boundary records");
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "native_f8_boundary_final_edges: " << e.what()
              << "\nPARTIAL_OUTPUT_NOT_VALID\n";
    return 2;
  }
}
