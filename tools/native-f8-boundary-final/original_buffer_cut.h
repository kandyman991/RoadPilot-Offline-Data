#pragma once

// Original buffered footprint crossing: a lightweight spatial filter INSIDE
// the same read-only native GraphReader source producer. Never enumerates
// tiles beyond the source's selected boundary tile set. Never chooses an
// arbitrary GPS waypoint; the true GraphId end node remains the handoff X.
#include <boost/geometry.hpp>
#include <boost/geometry/geometries/point_xy.hpp>
#include <boost/geometry/index/rtree.hpp>
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iterator>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace roadpilot_cut {
namespace bg = boost::geometry;
namespace bgi = boost::geometry::index;
using Point = bg::model::d2::point_xy<double>;
using Line = bg::model::segment<Point>;
using Box = bg::model::box<Point>;
using Polygon = bg::model::polygon<Point>;
using Area = bg::model::multi_polygon<Polygon>;
using IndexEntry = std::pair<Box, std::size_t>;

struct OriginalCut {
  Area area;
  std::vector<Line> segments;
  bgi::rtree<IndexEntry, bgi::quadratic<16>> index;

  explicit OriginalCut(const std::string& buffer_path,
                       const std::string& shared_cut_path = "") {
    boost::property_tree::ptree root;
    boost::property_tree::read_json(buffer_path, root);
    const std::string type = root.get<std::string>("geometry.type");
    if (root.get<std::string>("type") != "Feature" ||
        (type != "Polygon" && type != "MultiPolygon") ||
        root.get<double>("properties.borderBufferKm") != 25.0)
      throw std::runtime_error("Expected original 25-km Polygon/MultiPolygon footprint");
    auto read_ring = [](const boost::property_tree::ptree& ptree, auto& ring) {
      for (const auto& point : ptree) {
        const auto& coordinates = point.second;
        if (coordinates.size() < 2) throw std::runtime_error("Invalid source buffer coordinate");
        auto it = coordinates.begin();
        const double lon = it++->second.get_value<double>();
        const double lat = it->second.get_value<double>();
        if (!std::isfinite(lon) || !std::isfinite(lat) ||
            std::abs(lat) > 90 || std::abs(lon) > 180)
          throw std::runtime_error("Bad source buffer GPS coordinate");
        ring.emplace_back(lon, lat);
      }
      if (ring.size() < 4) throw std::runtime_error("Invalid original buffer ring");
    };
    auto read_polygon = [&](const boost::property_tree::ptree& rings) {
      Polygon polygon;
      bool outer = true;
      for (const auto& ring_entry : rings) {
        if (outer) {
          read_ring(ring_entry.second, polygon.outer());
          outer = false;
        } else {
          polygon.inners().emplace_back();
          read_ring(ring_entry.second, polygon.inners().back());
        }
      }
      if (outer) throw std::runtime_error("Missing original buffer exterior");
      bg::correct(polygon);
      if (!bg::is_valid(polygon)) throw std::runtime_error("Invalid original buffer topology");
      area.push_back(std::move(polygon));
    };
    const auto& coords = root.get_child("geometry.coordinates");
    if (type == "Polygon") read_polygon(coords);
    else for (const auto& poly : coords) read_polygon(poly.second);
    if (area.empty()) throw std::runtime_error("Empty original buffer footprint");
    for (const auto& polygon : area) {
      auto append = [&](const auto& ring) {
        for (std::size_t i = 1; i < ring.size(); ++i)
          segments.emplace_back(ring[i-1], ring[i]);
      };
      append(polygon.outer());
      for (const auto& hole : polygon.inners()) append(hole);
    }
    if (segments.empty()) throw std::runtime_error("No buffer boundary segments");
    if (!shared_cut_path.empty()) {
      // The shared geometry is A's ORIGINAL outer 25-km cutoff intersected
      // with B's own SHA-verified original buffered coverage. It is derived
      // only from the two immutable original GeoJSONs; never from OSM roads,
      // region names, arbitrary sampling or the nominal border.
      boost::property_tree::ptree shared;
      boost::property_tree::read_json(shared_cut_path, shared);
      const auto& geom = shared.get_child("geometry");
      const auto type = geom.get<std::string>("type");
      if (shared.get<std::string>("type") != "Feature" ||
          (type != "LineString" && type != "MultiLineString"))
        throw std::runtime_error("Expected derived shared outer-cut LineString/MultiLineString");
      std::vector<Line> bounded;
      auto parse_line = [&](const boost::property_tree::ptree& points) {
        bool seen = false;
        Point prior;
        for (const auto& item : points) {
          const auto& coordinates = item.second;
          if (coordinates.size() != 2)
            throw std::runtime_error("Invalid derived shared-cut coordinate");
          auto it = coordinates.begin();
          const auto lon = it++->second.get_value<double>();
          const auto lat = it->second.get_value<double>();
          if (!std::isfinite(lon) || !std::isfinite(lat) ||
              std::abs(lat) > 90 || std::abs(lon) > 180)
            throw std::runtime_error("Invalid derived shared-cut GPS coordinate");
          const Point current(lon, lat);
          if (seen && !bg::equals(current, prior))
            bounded.emplace_back(prior, current);
          prior = current;
          seen = true;
        }
        if (!seen) throw std::runtime_error("Empty shared-cut geometry");
      };
      const auto& coords = geom.get_child("coordinates");
      if (type == "LineString") parse_line(coords);
      else for (const auto& line : coords) parse_line(line.second);
      if (bounded.empty()) throw std::runtime_error("No real shared buffer cutoff lines");
      segments = std::move(bounded);
    }
    std::vector<IndexEntry> entries;
    entries.reserve(segments.size());
    for (std::size_t i = 0; i < segments.size(); ++i) {
      Box bounds;
      bg::envelope(segments[i], bounds);
      entries.emplace_back(bounds, i);
    }
    index = decltype(index)(entries.begin(), entries.end());
  }

  template <typename Shape>
  bool intersects(const Shape& native_shape) const {
    if (native_shape.size() < 2) return false;
    for (std::size_t i = 1; i < native_shape.size(); ++i) {
      const auto& a = native_shape[i-1];
      const auto& b = native_shape[i];
      if (!std::isfinite(a.lat()) || !std::isfinite(a.lng()) ||
          !std::isfinite(b.lat()) || !std::isfinite(b.lng()))
        throw std::runtime_error("Invalid original native directed geometry");
      const Line segment(Point(a.lng(), a.lat()), Point(b.lng(), b.lat()));
      Box bounds;
      bg::envelope(segment, bounds);
      std::vector<IndexEntry> hits;
      index.query(bgi::intersects(bounds), std::back_inserter(hits));
      for (const auto& hit : hits) {
        if (bg::intersects(segment, segments.at(hit.second))) return true;
      }
    }
    return false;
  }

  template <typename Shape>
  std::string direction(const Shape& native_shape) const {
    if (native_shape.size() < 2) return "AMBIGUOUS";
    const auto& a = native_shape.front();
    const auto& b = native_shape.back();
    const Point start(a.lng(), a.lat()), end(b.lng(), b.lat());
    // Covers boundary points too: if either endpoint is exactly on the
    // cutoff, the direction is deliberately unresolved, not guessed.
    if (bg::covered_by(start, area) && !bg::within(start, area)) return "AMBIGUOUS";
    if (bg::covered_by(end, area) && !bg::within(end, area)) return "AMBIGUOUS";
    const bool inside_a = bg::within(start, area);
    const bool inside_b = bg::within(end, area);
    if (inside_a && !inside_b) return "OUTWARD";
    if (!inside_a && inside_b) return "INWARD";
    return "AMBIGUOUS";
  }
};

}  // namespace roadpilot_cut
