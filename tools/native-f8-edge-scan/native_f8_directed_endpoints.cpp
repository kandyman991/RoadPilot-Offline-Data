// Read-only exact directed endpoint extractor for F8 terminal research.
// NOT a handoff producer: the deadend flag does not establish cross-graph
// continuity, and graph-local GraphIds are never compared across graphs.
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/midgard/logging.h>

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
  if (argc != 3) {
    std::cerr << "usage: native_f8_directed_endpoints <valhalla.json> <graph_ids.txt>\n";
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
                << ",\"reverseAccess\":" << edge->reverseaccess()
                << "}\n";
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
