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
  const bool include_continuations = argc == 4 && std::string(argv[3]) == "--continuations";
  const bool include_geometry = argc == 4 && std::string(argv[3]) == "--geometry";
  if (argc != 3 && !include_continuations && !include_geometry) {
    std::cerr << "usage: native_f8_directed_endpoints <valhalla.json> <graph_ids.txt> [--continuations|--geometry]\n";
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
