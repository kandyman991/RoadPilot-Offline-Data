#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <rapidjson/document.h>
#include <rapidjson/prettywriter.h>
#include <rapidjson/stringbuffer.h>
#include <valhalla/baldr/graphconstants.h>
#include <valhalla/baldr/graphreader.h>
#include <valhalla/loki/worker.h>
#include <valhalla/thor/worker.h>
#include <valhalla/worker.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace {

constexpr double kDefaultMaxSeamMeters = 5.0;

struct Coord {
  double lat;
  double lon;
};

struct CorrelationData {
  uint64_t graph_id;
  double lat;
  double lon;
  double percent_along;
  double distance_meters;
  double heading_degrees;
  int inbound_reach;
  int outbound_reach;
};

struct GraphRuntime {
  boost::property_tree::ptree config;
  std::shared_ptr<valhalla::baldr::GraphReader> reader;
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

GraphRuntime load_graph_runtime(const std::string& config_path) {
  GraphRuntime runtime;
  boost::property_tree::read_json(config_path, runtime.config);
  const auto mjolnir = runtime.config.get_child_optional("mjolnir");
  if (!mjolnir) {
    throw std::runtime_error(
        "Valhalla config " + config_path + " has no mjolnir section");
  }
  runtime.reader =
      std::make_shared<valhalla::baldr::GraphReader>(runtime.config.get_child("mjolnir"));
  return runtime;
}

double approximate_meters(const Coord& a, const Coord& b) {
  constexpr double meters_per_degree = 111320.0;
  const double mean_lat = (a.lat + b.lat) * 0.5 * M_PI / 180.0;
  const double dy = (b.lat - a.lat) * meters_per_degree;
  const double dx =
      (b.lon - a.lon) * meters_per_degree * std::cos(mean_lat);
  return std::sqrt(dx * dx + dy * dy);
}

Coord midpoint(const Coord& a, const Coord& b) {
  return {(a.lat + b.lat) * 0.5, (a.lon + b.lon) * 0.5};
}

Coord get_coord(const rapidjson::Value& object, const char* name) {
  if (!object.HasMember(name) || !object[name].IsObject()) {
    throw std::runtime_error(std::string("Missing coordinate ") + name);
  }
  const auto& c = object[name];
  if (!c.HasMember("lat") || !c["lat"].IsNumber() ||
      !c.HasMember("lng") || !c["lng"].IsNumber()) {
    throw std::runtime_error(std::string("Invalid coordinate ") + name);
  }
  return {c["lat"].GetDouble(), c["lng"].GetDouble()};
}

std::vector<valhalla::midgard::PointLL> directed_shape(
    valhalla::baldr::GraphReader& reader,
    const uint64_t graph_id_value) {
  const valhalla::baldr::GraphId graph_id(graph_id_value);
  auto tile = reader.GetGraphTile(graph_id);
  if (!tile) throw std::runtime_error("Exact edge tile is unavailable");
  const auto* edge = tile->directededge(graph_id);
  if (
      edge == nullptr ||
      edge->is_shortcut() ||
      edge->IsTransitLine() ||
      !edge->is_road()) {
    throw std::runtime_error("Exact GraphId is not a routable road edge");
  }
  auto shape = tile->edgeinfo(edge).shape();
  if (!edge->forward()) std::reverse(shape.begin(), shape.end());
  if (shape.size() < 2) {
    throw std::runtime_error("Exact road edge has no usable geometry");
  }
  return shape;
}

struct ProjectedPoint {
  Coord coordinate;
  double percent_along;
};

ProjectedPoint project_requested_point_on_edge(
    const std::vector<valhalla::midgard::PointLL>& shape,
    const Coord& requested) {
  if (shape.size() < 2) return {requested, 0.0};

  constexpr double meters_per_degree = 111320.0;
  double travelled = 0.0;
  double total = 0.0;
  double best_travelled = 0.0;
  double best_distance = std::numeric_limits<double>::max();
  Coord best = requested;

  for (size_t i = 1; i < shape.size(); ++i) {
    const Coord a{shape[i - 1].lat(), shape[i - 1].lng()};
    const Coord b{shape[i].lat(), shape[i].lng()};
    const double segment = approximate_meters(a, b);
    if (segment <= 0.001) continue;

    const double reference_lat =
        (a.lat + b.lat + requested.lat) / 3.0 * M_PI / 180.0;
    const double lon_scale = std::cos(reference_lat);
    const double sx = (b.lon - a.lon) * meters_per_degree * lon_scale;
    const double sy = (b.lat - a.lat) * meters_per_degree;
    const double qx =
        (requested.lon - a.lon) * meters_per_degree * lon_scale;
    const double qy = (requested.lat - a.lat) * meters_per_degree;
    const double segment_sq = sx * sx + sy * sy;
    const double fraction =
        segment_sq <= 1e-9
            ? 0.0
            : std::clamp((qx * sx + qy * sy) / segment_sq, 0.0, 1.0);

    const Coord projected{
        a.lat + (b.lat - a.lat) * fraction,
        a.lon + (b.lon - a.lon) * fraction};
    const double distance = approximate_meters(projected, requested);
    if (distance < best_distance) {
      best_distance = distance;
      best = projected;
      best_travelled = travelled + segment * fraction;
    }

    travelled += segment;
    total += segment;
  }

  if (total <= 0.001) return {best, 0.0};
  return {
      best,
      std::clamp(best_travelled / total, 0.000001, 0.999999)};
}

uint32_t mode_access_mask(const std::string& mode) {
  if (mode == "MOTORCYCLE") {
    return valhalla::baldr::kMotorcycleAccess;
  }
  if (mode == "CAR") {
    return valhalla::baldr::kAutoAccess;
  }
  throw std::runtime_error("Unsupported travel mode " + mode);
}

const char* mode_costing(const std::string& mode) {
  if (mode == "MOTORCYCLE") return "motorcycle";
  if (mode == "CAR") return "auto";
  throw std::runtime_error("Unsupported travel mode " + mode);
}

std::string route_request_json(
    const Coord& start,
    const Coord& end,
    const std::string& mode) {
  std::ostringstream json;
  json.precision(12);
  json << "{\"locations\":["
       << "{\"lat\":" << start.lat << ",\"lon\":" << start.lon << "},"
       << "{\"lat\":" << end.lat << ",\"lon\":" << end.lon << "}"
       << "],\"costing\":\"" << mode_costing(mode) << "\"}";
  return json.str();
}

void prepare_exact_location_for_loki(
    valhalla::Location& location,
    valhalla::baldr::GraphReader& reader,
    const uint64_t graph_id_value) {
  const auto shape = directed_shape(reader, graph_id_value);
  const Coord requested{location.ll().lat(), location.ll().lng()};
  const auto target = project_requested_point_on_edge(shape, requested);

  location.mutable_ll()->set_lat(target.coordinate.lat);
  location.mutable_ll()->set_lng(target.coordinate.lon);
  location.mutable_display_ll()->set_lat(target.coordinate.lat);
  location.mutable_display_ll()->set_lng(target.coordinate.lon);
  location.set_preferred_side(valhalla::Location_PreferredSide_either);
  location.set_node_snap_tolerance(0);
  location.set_minimum_reachability(0);
  location.set_radius(5);
}

CorrelationData retain_stored_exact_correlation(
    valhalla::Location& location,
    valhalla::baldr::GraphReader& reader,
    const uint64_t graph_id_value,
    const uint32_t required_access_mask) {
  const valhalla::baldr::GraphId graph_id(graph_id_value);
  auto tile = reader.GetGraphTile(graph_id);
  if (!tile) throw std::runtime_error("Exact correlation tile is unavailable");
  const auto* edge = tile->directededge(graph_id);
  if (edge == nullptr) {
    throw std::runtime_error("Exact correlation edge is unavailable");
  }
  if ((edge->forwardaccess() & required_access_mask) == 0) {
    throw std::runtime_error(
        "Stored exact DirectedEdge does not allow requested travel mode");
  }

  std::vector<valhalla::PathEdge> exact_edges;
  for (const auto& candidate : location.correlation().edges()) {
    if (candidate.graph_id() == graph_id.value) {
      exact_edges.push_back(candidate);
    }
  }
  if (exact_edges.empty()) {
    std::ostringstream error;
    error << "Loki did not correlate required exact edge " << graph_id.value;
    throw std::runtime_error(error.str());
  }

  auto* correlation = location.mutable_correlation();
  correlation->clear_edges();
  correlation->clear_filtered_edges();
  for (const auto& candidate : exact_edges) {
    correlation->add_edges()->CopyFrom(candidate);
  }
  correlation->mutable_projected_ll()->CopyFrom(exact_edges.front().ll());

  const auto& selected = exact_edges.front();
  return {
      selected.graph_id(),
      selected.ll().lat(),
      selected.ll().lng(),
      selected.percent_along(),
      selected.distance(),
      selected.heading(),
      selected.inbound_reach(),
      selected.outbound_reach()};
}

CorrelationData prove_local_route(
    GraphRuntime& runtime,
    const Coord& start,
    const Coord& end,
    const uint64_t exact_graph_id,
    const bool exact_is_start,
    const std::string& mode) {
  valhalla::Api api;
  valhalla::ParseApi(
      route_request_json(start, end, mode),
      valhalla::Options::route,
      api);
  auto* options = api.mutable_options();
  if (options->locations_size() != 2) {
    throw std::runtime_error("Exact local proof requires two route locations");
  }

  auto* exact_location =
      options->mutable_locations(exact_is_start ? 0 : 1);
  prepare_exact_location_for_loki(
      *exact_location, *runtime.reader, exact_graph_id);

  valhalla::loki::loki_worker_t loki(runtime.config, runtime.reader);
  valhalla::thor::thor_worker_t thor(runtime.config, runtime.reader);

  loki.route(api);
  CorrelationData exact = retain_stored_exact_correlation(
      *api.mutable_options()->mutable_locations(exact_is_start ? 0 : 1),
      *runtime.reader,
      exact_graph_id,
      mode_access_mask(mode));

  thor.route(api);
  return exact;
}

bool supports_mode(const rapidjson::Value& candidate, const std::string& mode) {
  if (
      !candidate.HasMember("commonTravelModes") ||
      !candidate["commonTravelModes"].IsArray()) {
    return false;
  }
  for (const auto& item : candidate["commonTravelModes"].GetArray()) {
    if (item.IsString() && mode == item.GetString()) return true;
  }
  return false;
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

struct EdgeMetadata {
  uint64_t graph_id;
  uint64_t opposing_graph_id;
  uint64_t source_node_graph_id;
  uint64_t end_node_graph_id;
  uint64_t way_id;
  uint32_t forward_access;
  uint32_t reverse_access;
  uint32_t road_class;
  uint32_t use;
  std::vector<std::string> road_names;
  std::vector<std::string> road_refs;
};

EdgeMetadata inspect_edge_metadata(
    valhalla::baldr::GraphReader& reader,
    const uint64_t graph_id_value) {
  const valhalla::baldr::GraphId graph_id(graph_id_value);
  auto tile = reader.GetGraphTile(graph_id);
  if (!tile) throw std::runtime_error("Bound edge tile is unavailable");
  const auto* edge = tile->directededge(graph_id);
  if (
      edge == nullptr ||
      edge->is_shortcut() ||
      edge->IsTransitLine() ||
      !edge->is_road()) {
    throw std::runtime_error("Bound GraphId is not a routable road edge");
  }

  const valhalla::baldr::DirectedEdge* opposing = nullptr;
  const auto opposing_id = reader.GetOpposingEdgeId(graph_id, opposing, tile);
  if (!opposing_id.is_valid() || opposing == nullptr) {
    throw std::runtime_error("Bound edge has no opposing DirectedEdge");
  }
  const auto source_node = opposing->endnode();
  const auto end_node = edge->endnode();
  if (!source_node.is_valid() || !end_node.is_valid()) {
    throw std::runtime_error("Bound edge has invalid endpoint node");
  }

  const auto info = tile->edgeinfo(edge);
  std::vector<std::string> names;
  std::vector<std::string> refs;
  for (const auto& name_type : info.GetNamesAndTypes(false)) {
    const auto& value = std::get<0>(name_type);
    if (std::get<1>(name_type)) refs.push_back(value);
    else names.push_back(value);
  }

  return {
      graph_id.value,
      opposing_id.value,
      source_node.value,
      end_node.value,
      info.wayid(),
      edge->forwardaccess(),
      edge->reverseaccess(),
      static_cast<uint32_t>(edge->classification()),
      static_cast<uint32_t>(edge->use()),
      std::move(names),
      std::move(refs)};
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

rapidjson::Value binding_json(
    GraphRuntime& runtime,
    const std::string& region_id,
    const std::string& graph_fingerprint,
    const CorrelationData& correlation,
    rapidjson::Document::AllocatorType& allocator) {
  const auto metadata =
      inspect_edge_metadata(*runtime.reader, correlation.graph_id);
  rapidjson::Value edge(rapidjson::kObjectType);
  edge.AddMember("correlationRank", 0, allocator);
  edge.AddMember("graphId", metadata.graph_id, allocator);
  edge.AddMember("opposingGraphId", metadata.opposing_graph_id, allocator);
  edge.AddMember("sourceNodeGraphId", metadata.source_node_graph_id, allocator);
  edge.AddMember("endNodeGraphId", metadata.end_node_graph_id, allocator);
  edge.AddMember("wayId", metadata.way_id, allocator);
  edge.AddMember(
      "correlatedCoordinate",
      coord_json({correlation.lat, correlation.lon}, allocator),
      allocator);
  edge.AddMember("percentAlong", correlation.percent_along, allocator);
  edge.AddMember("distanceMeters", correlation.distance_meters, allocator);
  edge.AddMember("headingDegrees", correlation.heading_degrees, allocator);
  edge.AddMember("inboundReach", correlation.inbound_reach, allocator);
  edge.AddMember("outboundReach", correlation.outbound_reach, allocator);
  edge.AddMember("forwardAccess", metadata.forward_access, allocator);
  edge.AddMember("reverseAccess", metadata.reverse_access, allocator);
  edge.AddMember("roadClass", metadata.road_class, allocator);
  edge.AddMember("use", metadata.use, allocator);
  edge.AddMember(
      "roadNames", strings_json(metadata.road_names, allocator), allocator);
  edge.AddMember(
      "roadRefs", strings_json(metadata.road_refs, allocator), allocator);

  rapidjson::Value candidates(rapidjson::kArrayType);
  candidates.PushBack(edge, allocator);

  rapidjson::Value binding(rapidjson::kObjectType);
  binding.AddMember(
      "regionId", json_string(region_id, allocator), allocator);
  binding.AddMember(
      "graphFingerprint",
      json_string(graph_fingerprint, allocator),
      allocator);
  binding.AddMember(
      "proofCoordinate",
      coord_json({correlation.lat, correlation.lon}, allocator),
      allocator);
  binding.AddMember("candidates", candidates, allocator);
  return binding;
}

std::string required_string(
    const rapidjson::Value& root,
    const char* name) {
  if (!root.HasMember(name) || !root[name].IsString()) {
    throw std::runtime_error(std::string("Candidate catalog missing ") + name);
  }
  return root[name].GetString();
}

struct Args {
  std::string from_config;
  std::string to_config;
  std::string candidates;
  std::string mode;
  std::string output;
  double max_seam_meters = kDefaultMaxSeamMeters;
};

Args parse_args(int argc, char** argv) {
  Args args;
  for (int i = 1; i < argc; ++i) {
    const std::string key = argv[i];
    auto next = [&]() -> std::string {
      if (++i >= argc) throw std::runtime_error("Missing value after " + key);
      return argv[i];
    };
    if (key == "--from-config") args.from_config = next();
    else if (key == "--to-config") args.to_config = next();
    else if (key == "--candidates") args.candidates = next();
    else if (key == "--mode") args.mode = next();
    else if (key == "--output") args.output = next();
    else if (key == "--max-seam-meters") {
      args.max_seam_meters = std::stod(next());
    } else {
      throw std::runtime_error("Unknown argument " + key);
    }
  }
  if (
      args.from_config.empty() ||
      args.to_config.empty() ||
      args.candidates.empty() ||
      args.mode.empty() ||
      args.output.empty()) {
    throw std::runtime_error(
        "Usage: roadpilot-transition-probe "
        "--from-config A.json --to-config B.json "
        "--candidates candidates.json --mode MOTORCYCLE|CAR "
        "--output proof-results.json [--max-seam-meters 5]");
  }
  if (args.max_seam_meters <= 0.0) {
    throw std::runtime_error("--max-seam-meters must be positive");
  }
  (void)mode_access_mask(args.mode);
  return args;
}

} // namespace

int main(int argc, char** argv) {
  try {
    const Args args = parse_args(argc, argv);

    rapidjson::Document catalog;
    const std::string candidate_text = read_file(args.candidates);
    catalog.Parse(candidate_text.c_str());
    if (catalog.HasParseError() || !catalog.IsObject()) {
      throw std::runtime_error("Could not parse candidate catalog JSON");
    }
    if (
        required_string(catalog, "schema") != "roadpilot.transition-candidates" ||
        !catalog.HasMember("version") ||
        !catalog["version"].IsInt() ||
        catalog["version"].GetInt() != 1) {
      throw std::runtime_error("Unsupported candidate catalog schema/version");
    }

    const std::string from_region = required_string(catalog, "fromRegionId");
    const std::string to_region = required_string(catalog, "toRegionId");
    const std::string from_fingerprint =
        required_string(catalog, "fromGraphFingerprint");
    const std::string to_fingerprint =
        required_string(catalog, "toGraphFingerprint");

    if (
        !catalog.HasMember("candidates") ||
        !catalog["candidates"].IsArray()) {
      throw std::runtime_error("Candidate catalog has no candidates array");
    }

    GraphRuntime from_runtime = load_graph_runtime(args.from_config);
    GraphRuntime to_runtime = load_graph_runtime(args.to_config);

    rapidjson::Document output;
    output.SetObject();
    auto& allocator = output.GetAllocator();
    output.AddMember(
        "schema",
        json_string("roadpilot.transition-proof-results", allocator),
        allocator);
    output.AddMember("version", 1, allocator);
    output.AddMember(
        "fromRegionId", json_string(from_region, allocator), allocator);
    output.AddMember(
        "toRegionId", json_string(to_region, allocator), allocator);
    output.AddMember(
        "fromGraphFingerprint",
        json_string(from_fingerprint, allocator),
        allocator);
    output.AddMember(
        "toGraphFingerprint",
        json_string(to_fingerprint, allocator),
        allocator);

    rapidjson::Value results(rapidjson::kArrayType);
    size_t accepted_count = 0;
    size_t rejected_count = 0;

    for (const auto& candidate : catalog["candidates"].GetArray()) {
      if (!candidate.IsObject() || !candidate.HasMember("id") ||
          !candidate["id"].IsString()) {
        continue;
      }
      if (!supports_mode(candidate, args.mode)) continue;

      const std::string candidate_id = candidate["id"].GetString();
      rapidjson::Value result(rapidjson::kObjectType);
      result.AddMember(
          "candidateId", json_string(candidate_id, allocator), allocator);
      result.AddMember(
          "bindingMode", json_string(args.mode, allocator), allocator);

      try {
        if (
            !candidate.HasMember("fromEdge") ||
            !candidate["fromEdge"].IsObject() ||
            !candidate.HasMember("toEdge") ||
            !candidate["toEdge"].IsObject()) {
          throw std::runtime_error("Candidate is missing fromEdge/toEdge");
        }
        const auto& from_edge = candidate["fromEdge"];
        const auto& to_edge = candidate["toEdge"];

        if (
            !from_edge.HasMember("opposingGraphId") ||
            !from_edge["opposingGraphId"].IsUint64() ||
            !to_edge.HasMember("graphId") ||
            !to_edge["graphId"].IsUint64()) {
          throw std::runtime_error(
              "Candidate does not contain exact graph identities");
        }

        // Scanner edges point boundary -> interior. A -> B therefore becomes
        // A opposing edge (interior -> seam) and B stored edge (seam -> interior).
        // The artifact is normalized to STORED/STORED, exactly like learned F8 replay.
        const uint64_t from_outbound_graph_id =
            from_edge["opposingGraphId"].GetUint64();
        const uint64_t to_inbound_graph_id =
            to_edge["graphId"].GetUint64();

        const Coord from_anchor =
            get_coord(from_edge, "anchorCoordinate");
        const Coord to_anchor =
            get_coord(to_edge, "anchorCoordinate");
        const Coord requested_seam = midpoint(from_anchor, to_anchor);
        const Coord from_inner =
            get_coord(from_edge, "innerCoordinate");
        const Coord to_inner =
            get_coord(to_edge, "innerCoordinate");

        const CorrelationData from_proof = prove_local_route(
            from_runtime,
            from_inner,
            requested_seam,
            from_outbound_graph_id,
            false,
            args.mode);
        const CorrelationData to_proof = prove_local_route(
            to_runtime,
            requested_seam,
            to_inner,
            to_inbound_graph_id,
            true,
            args.mode);

        const double seam_gap = approximate_meters(
            {from_proof.lat, from_proof.lon},
            {to_proof.lat, to_proof.lon});
        if (seam_gap > args.max_seam_meters) {
          std::ostringstream error;
          error.precision(4);
          error << "Exact proven seam gap " << seam_gap
                << "m exceeds " << args.max_seam_meters << "m";
          throw std::runtime_error(error.str());
        }

        result.AddMember("accepted", true, allocator);
        result.AddMember("seamGapMeters", seam_gap, allocator);
        result.AddMember(
            "fromBinding",
            binding_json(
                from_runtime,
                from_region,
                from_fingerprint,
                from_proof,
                allocator),
            allocator);
        result.AddMember(
            "toBinding",
            binding_json(
                to_runtime,
                to_region,
                to_fingerprint,
                to_proof,
                allocator),
            allocator);
        ++accepted_count;
      } catch (const std::exception& error) {
        result.AddMember("accepted", false, allocator);
        result.AddMember(
            "failureReason",
            json_string(error.what(), allocator),
            allocator);
        ++rejected_count;
      }

      results.PushBack(result, allocator);
    }

    output.AddMember("results", results, allocator);

    rapidjson::StringBuffer buffer;
    rapidjson::PrettyWriter<rapidjson::StringBuffer> writer(buffer);
    output.Accept(writer);
    write_file(args.output, std::string(buffer.GetString()) + "\n");

    std::cout << from_region << " -> " << to_region << " " << args.mode
              << ": accepted=" << accepted_count
              << " rejected=" << rejected_count << "\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "roadpilot-transition-probe: " << error.what() << "\n";
    return 1;
  }
}
