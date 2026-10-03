#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <rapidjson/document.h>
#include <rapidjson/prettywriter.h>
#include <rapidjson/stringbuffer.h>
#include <valhalla/baldr/graphconstants.h>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/baldr/tilehierarchy.h>
#include <valhalla/midgard/aabb2.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

struct Coord {
  double lat;
  double lon;
};

struct EdgePoint {
  Coord coordinate;
  double percent_along;
};

struct Window {
  double min_lat;
  double max_lat;
  double min_lon;
  double max_lon;
};

std::string read_file(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("Could not open " + path);
  std::ostringstream out;
  out << input.rdbuf();
  return out.str();
}

void write_file(const std::string& path, const std::string& text) {
  std::ofstream output(path);
  if (!output) throw std::runtime_error("Could not write " + path);
  output << text;
}

double approximate_meters(const Coord& a, const Coord& b) {
  constexpr double meters_per_degree = 111320.0;
  const double mean_lat = (a.lat + b.lat) * 0.5 * M_PI / 180.0;
  const double dy = (b.lat - a.lat) * meters_per_degree;
  const double dx =
      (b.lon - a.lon) * meters_per_degree * std::cos(mean_lat);
  return std::sqrt(dx * dx + dy * dy);
}

double heading_degrees(const Coord& from, const Coord& to) {
  const double mean_lat = (from.lat + to.lat) * 0.5 * M_PI / 180.0;
  const double x = (to.lon - from.lon) * std::cos(mean_lat);
  const double y = to.lat - from.lat;
  double degrees = std::atan2(x, y) * 180.0 / M_PI;
  if (degrees < 0.0) degrees += 360.0;
  return degrees;
}

EdgePoint inner_point_on_edge(
    const std::vector<valhalla::midgard::PointLL>& shape,
    const Coord& fallback) {
  if (shape.size() < 2) return {fallback, 0.0};

  double total = 0.0;
  for (size_t i = 1; i < shape.size(); ++i) {
    total += approximate_meters(
        {shape[i - 1].lat(), shape[i - 1].lng()},
        {shape[i].lat(), shape[i].lng()});
  }
  if (total <= 1.0) return {fallback, 0.0};

  const double target = std::min(120.0, total * 0.5);
  double travelled = 0.0;
  for (size_t i = 1; i < shape.size(); ++i) {
    const Coord a{shape[i - 1].lat(), shape[i - 1].lng()};
    const Coord b{shape[i].lat(), shape[i].lng()};
    const double segment = approximate_meters(a, b);
    if (segment <= 0.01) continue;
    if (travelled + segment >= target) {
      const double fraction = (target - travelled) / segment;
      return {
          {
              a.lat + (b.lat - a.lat) * fraction,
              a.lon + (b.lon - a.lon) * fraction,
          },
          std::clamp(target / total, 0.001, 0.999),
      };
    }
    travelled += segment;
  }

  return {
      {shape.back().lat(), shape.back().lng()},
      0.999,
  };
}

std::vector<valhalla::baldr::GraphId> road_tiles_in_window(
    valhalla::baldr::GraphReader& reader,
    const Window& window) {
  const valhalla::midgard::AABB2<valhalla::midgard::PointLL> bbox(
      window.min_lon,
      window.min_lat,
      window.max_lon,
      window.max_lat);
  std::vector<valhalla::baldr::GraphId> tile_ids;

  for (const auto& level : valhalla::baldr::TileHierarchy::levels()) {
    for (const auto id : level.tiles.TileList(bbox)) {
      const valhalla::baldr::GraphId tile_id(
          static_cast<uint32_t>(id), level.level, 0);
      if (reader.DoesTileExist(tile_id)) {
        tile_ids.push_back(tile_id);
      }
    }
  }
  return tile_ids;
}

std::vector<Window> load_windows(const std::string& path) {
  rapidjson::Document document;
  const std::string text = read_file(path);
  document.Parse(text.c_str());
  if (document.HasParseError() || !document.IsObject()) {
    throw std::runtime_error("Could not parse frontier windows JSON");
  }
  if (
      !document.HasMember("schema") ||
      !document["schema"].IsString() ||
      std::string(document["schema"].GetString()) !=
          "roadpilot.shared-frontier-windows" ||
      !document.HasMember("version") ||
      !document["version"].IsInt() ||
      document["version"].GetInt() != 1 ||
      !document.HasMember("windows") ||
      !document["windows"].IsArray()) {
    throw std::runtime_error("Unsupported shared-frontier window schema");
  }

  std::vector<Window> windows;
  for (const auto& item : document["windows"].GetArray()) {
    if (!item.IsObject()) continue;
    windows.push_back({
        item["minLat"].GetDouble(),
        item["maxLat"].GetDouble(),
        item["minLng"].GetDouble(),
        item["maxLng"].GetDouble(),
    });
  }
  if (windows.empty()) {
    throw std::runtime_error("Frontier window file is empty");
  }
  return windows;
}

rapidjson::Value json_string(
    const std::string& text,
    rapidjson::Document::AllocatorType& allocator) {
  return rapidjson::Value(
      text.c_str(),
      static_cast<rapidjson::SizeType>(text.size()),
      allocator);
}

rapidjson::Value coord_json(
    const Coord& coordinate,
    rapidjson::Document::AllocatorType& allocator) {
  rapidjson::Value result(rapidjson::kObjectType);
  result.AddMember("lat", coordinate.lat, allocator);
  result.AddMember("lng", coordinate.lon, allocator);
  return result;
}

rapidjson::Value strings_json(
    const std::vector<std::string>& values,
    rapidjson::Document::AllocatorType& allocator) {
  rapidjson::Value result(rapidjson::kArrayType);
  for (const auto& value : values) {
    result.PushBack(json_string(value, allocator), allocator);
  }
  return result;
}

rapidjson::Value modes_json(
    const uint32_t forward_access,
    const uint32_t reverse_access,
    rapidjson::Document::AllocatorType& allocator) {
  const uint32_t access = forward_access | reverse_access;
  rapidjson::Value result(rapidjson::kArrayType);
  if ((access & valhalla::baldr::kMotorcycleAccess) != 0) {
    result.PushBack(json_string("MOTORCYCLE", allocator), allocator);
  }
  if ((access & valhalla::baldr::kAutoAccess) != 0) {
    result.PushBack(json_string("CAR", allocator), allocator);
  }
  return result;
}

struct Args {
  std::string config;
  std::string region_id;
  std::string fingerprint;
  std::string windows;
  std::string output;
};

Args parse_args(int argc, char** argv) {
  Args args;
  for (int i = 1; i < argc; ++i) {
    const std::string key = argv[i];
    auto next = [&]() -> std::string {
      if (++i >= argc) throw std::runtime_error("Missing value after " + key);
      return argv[i];
    };
    if (key == "--config") args.config = next();
    else if (key == "--region-id") args.region_id = next();
    else if (key == "--fingerprint") args.fingerprint = next();
    else if (key == "--windows") args.windows = next();
    else if (key == "--output") args.output = next();
    else throw std::runtime_error("Unknown argument " + key);
  }
  if (
      args.config.empty() ||
      args.region_id.empty() ||
      args.fingerprint.empty() ||
      args.windows.empty() ||
      args.output.empty()) {
    throw std::runtime_error(
        "Usage: roadpilot-boundary-inventory "
        "--config graph.json --region-id REGION --fingerprint SHA "
        "--windows frontier-windows.json --output inventory.json");
  }
  return args;
}

} // namespace

int main(int argc, char** argv) {
  try {
    const Args args = parse_args(argc, argv);
    const auto windows = load_windows(args.windows);

    boost::property_tree::ptree config;
    boost::property_tree::read_json(args.config, config);
    if (!config.get_child_optional("mjolnir")) {
      throw std::runtime_error("Valhalla config has no mjolnir section");
    }
    valhalla::baldr::GraphReader reader(config.get_child("mjolnir"));

    rapidjson::Document output;
    output.SetObject();
    auto& allocator = output.GetAllocator();
    output.AddMember(
        "schema",
        json_string("roadpilot.boundary-edge-inventory", allocator),
        allocator);
    output.AddMember("version", 1, allocator);
    output.AddMember(
        "regionId", json_string(args.region_id, allocator), allocator);
    output.AddMember(
        "graphFingerprint", json_string(args.fingerprint, allocator), allocator);

    rapidjson::Value generator(rapidjson::kObjectType);
    generator.AddMember(
        "name",
        json_string("roadpilot-valhalla-boundary-inventory", allocator),
        allocator);
    generator.AddMember("version", json_string("1", allocator), allocator);
    output.AddMember("generator", generator, allocator);

    rapidjson::Value edges(rapidjson::kArrayType);
    std::unordered_set<uint64_t> emitted_graph_ids;

    for (const auto& window : windows) {
      for (const auto& tile_id : road_tiles_in_window(reader, window)) {
        auto tile = reader.GetGraphTile(tile_id);
        if (!tile) continue;
        const auto* header = tile->header();

        for (uint32_t node_index = 0; node_index < header->nodecount(); ++node_index) {
          const valhalla::baldr::GraphId node_id(
              tile->id().tileid(), tile->id().level(), node_index);
          const auto ll = tile->get_node_ll(node_id);
          const Coord anchor{ll.lat(), ll.lng()};
          if (
              anchor.lat < window.min_lat ||
              anchor.lat > window.max_lat ||
              anchor.lon < window.min_lon ||
              anchor.lon > window.max_lon) {
            continue;
          }

          const auto* node = tile->node(node_index);
          for (uint32_t offset = 0; offset < node->edge_count(); ++offset) {
            const valhalla::baldr::GraphId edge_id(
                tile->id().tileid(),
                tile->id().level(),
                node->edge_index() + offset);
            if (!emitted_graph_ids.insert(edge_id.value).second) continue;

            const auto* edge = tile->directededge(edge_id);
            if (
                edge == nullptr ||
                edge->is_shortcut() ||
                edge->IsTransitLine() ||
                !edge->is_road()) {
              continue;
            }

            const uint32_t forward_access = edge->forwardaccess();
            const uint32_t reverse_access = edge->reverseaccess();
            const uint32_t motorized =
                valhalla::baldr::kAutoAccess |
                valhalla::baldr::kMotorcycleAccess;
            if (((forward_access | reverse_access) & motorized) == 0) continue;

            const auto info = tile->edgeinfo(edge);
            const uint64_t way_id = info.wayid();
            if (way_id == 0) continue;

            const valhalla::baldr::DirectedEdge* opposing = nullptr;
            const auto opposing_id =
                reader.GetOpposingEdgeId(edge_id, opposing, tile);
            if (!opposing_id.is_valid() || opposing == nullptr) continue;

            const auto source_node = opposing->endnode();
            const auto end_node = edge->endnode();
            if (!source_node.is_valid() || !end_node.is_valid()) continue;

            auto shape = info.shape();
            if (!edge->forward()) std::reverse(shape.begin(), shape.end());
            if (shape.size() < 2) continue;
            const auto inner = inner_point_on_edge(shape, anchor);
            if (approximate_meters(anchor, inner.coordinate) < 1.0) continue;

            std::vector<std::string> names;
            std::vector<std::string> refs;
            for (const auto& name_type : info.GetNamesAndTypes(false)) {
              if (std::get<1>(name_type)) refs.push_back(std::get<0>(name_type));
              else names.push_back(std::get<0>(name_type));
            }
            std::sort(names.begin(), names.end());
            names.erase(std::unique(names.begin(), names.end()), names.end());
            std::sort(refs.begin(), refs.end());
            refs.erase(std::unique(refs.begin(), refs.end()), refs.end());

            rapidjson::Value item(rapidjson::kObjectType);
            item.AddMember("graphId", edge_id.value, allocator);
            item.AddMember("opposingGraphId", opposing_id.value, allocator);
            item.AddMember("sourceNodeGraphId", source_node.value, allocator);
            item.AddMember("endNodeGraphId", end_node.value, allocator);
            item.AddMember("wayId", way_id, allocator);
            item.AddMember("anchorCoordinate", coord_json(anchor, allocator), allocator);
            item.AddMember(
                "innerCoordinate", coord_json(inner.coordinate, allocator), allocator);
            item.AddMember(
                "headingDegrees",
                heading_degrees(anchor, inner.coordinate),
                allocator);
            item.AddMember("forwardAccess", forward_access, allocator);
            item.AddMember("reverseAccess", reverse_access, allocator);
            item.AddMember(
                "roadClass",
                static_cast<uint32_t>(edge->classification()),
                allocator);
            item.AddMember(
                "use", static_cast<uint32_t>(edge->use()), allocator);
            item.AddMember("roadNames", strings_json(names, allocator), allocator);
            item.AddMember("roadRefs", strings_json(refs, allocator), allocator);
            item.AddMember(
                "allowedTravelModes",
                modes_json(forward_access, reverse_access, allocator),
                allocator);
            edges.PushBack(item, allocator);
          }
        }
      }
    }

    output.AddMember("edges", edges, allocator);
    rapidjson::StringBuffer buffer;
    rapidjson::PrettyWriter<rapidjson::StringBuffer> writer(buffer);
    output.Accept(writer);
    write_file(args.output, std::string(buffer.GetString()) + "\n");

    std::cout << args.region_id << ": exported "
              << output["edges"].Size()
              << " motorized frontier DirectedEdges from "
              << windows.size() << " windows\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "roadpilot-boundary-inventory: " << error.what() << "\n";
    return 1;
  }
}
