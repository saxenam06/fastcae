// A design's distance field meshed by CGAL's mesher (Mesh_3), compiled: every question the mesher asks
// of the field - is this point inside, where does this segment cross the surface - is answered here by
// trilinear interpolation of the grid, never by Python. Element sizes are constants, or read from a
// second grid. The same mesher also meshes a closed triangulated surface - a CAD part's own - with its
// sharp edges kept, to the same sizes, so the two can be compared. Built into the WSL micromamba
// environment `fieldmesh` by build.sh beside it; driven by mesh_cgal.py and gate_cad.py.

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Labeled_mesh_domain_3.h>
#include <CGAL/Mesh_complex_3_in_triangulation_3.h>
#include <CGAL/Mesh_criteria_3.h>
#include <CGAL/Mesh_domain_with_polyline_features_3.h>
#include <CGAL/Mesh_triangulation_3.h>
#include <CGAL/Polygon_mesh_processing/orient_polygon_soup.h>
#include <CGAL/Polygon_mesh_processing/polygon_soup_to_polygon_mesh.h>
#include <CGAL/Polyhedral_mesh_domain_with_features_3.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/boost/graph/helpers.h>
#include <CGAL/exude_mesh_3.h>
#include <CGAL/make_mesh_3.h>
#include <CGAL/perturb_mesh_3.h>

#ifdef CGAL_LINKED_WITH_TBB
#include <tbb/global_control.h>
#endif

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <optional>
#include <stdexcept>
#include <unordered_map>
#include <vector>

namespace py = pybind11;
namespace params = CGAL::parameters;

using K = CGAL::Exact_predicates_inexact_constructions_kernel;
using Point = K::Point_3;
using FieldDomain = CGAL::Labeled_mesh_domain_3<K>;
// The field with lines the mesh must follow - the edges of the faces loads and supports go on.
using EdgedFieldDomain = CGAL::Mesh_domain_with_polyline_features_3<FieldDomain>;
using Polyline = std::vector<Point>;
using SurfaceMesh = CGAL::Surface_mesh<Point>;
using SurfaceDomain = CGAL::Polyhedral_mesh_domain_with_features_3<K, SurfaceMesh>;
using Floats = py::array_t<float, py::array::c_style | py::array::forcecast>;
using Doubles = py::array_t<double, py::array::c_style | py::array::forcecast>;
using Indices = py::array_t<std::int64_t, py::array::c_style | py::array::forcecast>;

// A scalar sampled on a regular grid in C order (the last index fastest), read by trilinear
// interpolation. Outside the grid it is `outside`, or the nearest value when clamped; with no grid, the
// constant `outside`.
struct Grid {
  const float* data = nullptr;
  std::int64_t nx = 0, ny = 0, nz = 0;
  double ox = 0, oy = 0, oz = 0, h = 1, outside = 0;
  bool clamp = false;

  double operator()(double x, double y, double z) const {
    if (data == nullptr) return outside;
    double u = (x - ox) / h, v = (y - oy) / h, w = (z - oz) / h;
    if (clamp) {
      u = std::clamp(u, 0.0, double(nx - 1) - 1e-9);
      v = std::clamp(v, 0.0, double(ny - 1) - 1e-9);
      w = std::clamp(w, 0.0, double(nz - 1) - 1e-9);
    } else if (!(u >= 0 && v >= 0 && w >= 0) || u >= nx - 1 || v >= ny - 1 || w >= nz - 1) {
      return outside;
    }
    const std::int64_t i = std::int64_t(u), j = std::int64_t(v), k = std::int64_t(w);
    const double a = u - i, b = v - j, c = w - k;
    const std::int64_t sy = nz, sx = ny * nz;
    const float* p = data + (i * ny + j) * nz + k;
    const double c00 = p[0] * (1 - c) + p[1] * c;
    const double c01 = p[sy] * (1 - c) + p[sy + 1] * c;
    const double c10 = p[sx] * (1 - c) + p[sx + 1] * c;
    const double c11 = p[sx + sy] * (1 - c) + p[sx + sy + 1] * c;
    return (c00 * (1 - b) + c01 * b) * (1 - a) + (c10 * (1 - b) + c11 * b) * a;
  }
};

Grid grid_of(const Floats& a, const std::array<double, 3>& origin, double spacing, double outside, bool clamp) {
  if (a.ndim() != 3 || a.shape(0) < 2 || a.shape(1) < 2 || a.shape(2) < 2)
    throw std::invalid_argument("a grid is a 3D array at least 2 points along each axis");
  return Grid{a.data(), a.shape(0), a.shape(1), a.shape(2), origin[0], origin[1], origin[2], spacing, outside, clamp};
}

// The signed distance, negative inside the part, counting the questions asked of it.
struct Field {
  Grid grid;
  std::atomic<std::int64_t>* asked;

  K::FT operator()(const Point& p) const {
    asked->fetch_add(1, std::memory_order_relaxed);
    return grid(p.x(), p.y(), p.z());
  }
};

// A criterion over space: `factor` times the size grid, or a constant (a grid with no data).
template <class DomainIndex>
struct Size {
  typedef K::FT FT;
  typedef Point Point_3;
  typedef DomainIndex Index;
  Grid grid;
  double factor = 1;

  FT operator()(const Point_3& p, const int, const Index&) const { return factor * grid(p.x(), p.y(), p.z()); }
};

// Where each criterion's size comes from: a constant, or factors of one element-size grid.
struct Sizing {
  std::optional<Grid> grid;

  template <class Index>
  Size<Index> of(double constant, double factor) const {
    if (grid && factor > 0) return Size<Index>{*grid, factor};
    return Size<Index>{Grid{nullptr, 0, 0, 0, 0, 0, 0, 1, constant, false}, 1};
  }
};

Sizing sizing_of(const std::optional<Floats>& sizes, const std::array<double, 3>& origin, double spacing) {
  if (!sizes) return Sizing{};
  return Sizing{grid_of(*sizes, origin, spacing, 0, true)};
}

struct Sliver {
  bool perturb = true, exude = true;
  double bound = 0, time_limit = 0;
};

struct Made {
  std::vector<double> xyz;
  std::vector<std::int64_t> tets;
  double refine = 0, perturb = 0, exude = 0;
  std::int64_t asked = 0;
};

// Refine, then push out slivers until every dihedral angle is above `sliver.bound` degrees, or for at
// most `sliver.time_limit` seconds a pass (0: while a step helps); the tets inside, as arrays.
template <class C3t3, class MeshDomain, class Criteria>
Made generate(const MeshDomain& domain, const Criteria& criteria, const Sliver& sliver) {
  using Clock = std::chrono::steady_clock;
  auto seconds = [](Clock::time_point a, Clock::time_point b) { return std::chrono::duration<double>(b - a).count(); };
  Made made;
  const auto t0 = Clock::now();
  C3t3 c3t3 = CGAL::make_mesh_3<C3t3>(domain, criteria, params::no_perturb().no_exude());
  const auto t1 = Clock::now();
  if (sliver.perturb)
    CGAL::perturb_mesh_3(c3t3, domain, params::sliver_bound(sliver.bound).time_limit(sliver.time_limit));
  const auto t2 = Clock::now();
  if (sliver.exude) CGAL::exude_mesh_3(c3t3, params::sliver_bound(sliver.bound).time_limit(sliver.time_limit));
  const auto t3 = Clock::now();
  made.refine = seconds(t0, t1);
  made.perturb = seconds(t1, t2);
  made.exude = seconds(t2, t3);

  std::unordered_map<const void*, std::int64_t> index;
  for (auto c = c3t3.cells_in_complex_begin(); c != c3t3.cells_in_complex_end(); ++c) {
    for (int m = 0; m < 4; ++m) {
      const auto v = c->vertex(m);
      const auto [at, fresh] = index.try_emplace(&*v, std::int64_t(index.size()));
      if (fresh) {
        const auto& p = v->point();
        made.xyz.insert(made.xyz.end(), {CGAL::to_double(p.x()), CGAL::to_double(p.y()), CGAL::to_double(p.z())});
      }
      made.tets.push_back(at->second);
    }
  }
  return made;
}

template <class Tag>
Made run_field(const Grid& sdf, const Sizing& sizing, double cell_size, double facet_size, double facet_distance,
               double cell_factor, double facet_factor, double distance_factor, double angle, double ratio,
               double error, const Sliver& sliver, int seed) {
  using Tr = typename CGAL::Mesh_triangulation_3<FieldDomain, CGAL::Default, Tag>::type;
  using C3t3 = CGAL::Mesh_complex_3_in_triangulation_3<Tr>;
  using Criteria = CGAL::Mesh_criteria_3<Tr>;
  using Index = FieldDomain::Index;

  std::atomic<std::int64_t> asked{0};
  const K::Iso_cuboid_3 box(Point(sdf.ox, sdf.oy, sdf.oz),
                            Point(sdf.ox + (sdf.nx - 1) * sdf.h, sdf.oy + (sdf.ny - 1) * sdf.h,
                                  sdf.oz + (sdf.nz - 1) * sdf.h));
  CGAL::get_default_random() = CGAL::Random(seed);
  FieldDomain domain =
      FieldDomain::create_implicit_mesh_domain(Field{sdf, &asked}, box, params::relative_error_bound(error));
  Criteria criteria(params::facet_angle(angle)
                        .facet_size(sizing.of<Index>(facet_size, facet_factor))
                        .facet_distance(sizing.of<Index>(facet_distance, distance_factor))
                        .cell_radius_edge_ratio(ratio)
                        .cell_size(sizing.of<Index>(cell_size, cell_factor)));
  Made made = generate<C3t3>(domain, criteria, sliver);
  made.asked = asked.load();
  return made;
}

// The same, with polylines the mesh must follow: vertices along them, edges between, so the faces they
// bound come out exactly - where the grid alone would round a sharp edge.
template <class Tag>
Made run_edged_field(const Grid& sdf, const std::vector<Polyline>& lines, const Sizing& sizing, double edge_size,
                     double cell_size, double facet_size, double facet_distance, double edge_factor,
                     double cell_factor, double facet_factor, double distance_factor, double angle, double ratio,
                     double error, const Sliver& sliver, int seed) {
  using Tr = typename CGAL::Mesh_triangulation_3<EdgedFieldDomain, CGAL::Default, Tag>::type;
  using C3t3 =
      CGAL::Mesh_complex_3_in_triangulation_3<Tr, EdgedFieldDomain::Corner_index, EdgedFieldDomain::Curve_index>;
  using Criteria = CGAL::Mesh_criteria_3<Tr>;
  using Index = EdgedFieldDomain::Index;

  std::atomic<std::int64_t> asked{0};
  const K::Iso_cuboid_3 box(Point(sdf.ox, sdf.oy, sdf.oz),
                            Point(sdf.ox + (sdf.nx - 1) * sdf.h, sdf.oy + (sdf.ny - 1) * sdf.h,
                                  sdf.oz + (sdf.nz - 1) * sdf.h));
  CGAL::get_default_random() = CGAL::Random(seed);
  EdgedFieldDomain domain(
      FieldDomain::create_implicit_mesh_domain(Field{sdf, &asked}, box, params::relative_error_bound(error)));
  domain.add_features(lines.begin(), lines.end());
  Criteria criteria(params::edge_size(sizing.of<Index>(edge_size, edge_factor))
                        .facet_angle(angle)
                        .facet_size(sizing.of<Index>(facet_size, facet_factor))
                        .facet_distance(sizing.of<Index>(facet_distance, distance_factor))
                        .cell_radius_edge_ratio(ratio)
                        .cell_size(sizing.of<Index>(cell_size, cell_factor)));
  Made made = generate<C3t3>(domain, criteria, sliver);
  made.asked = asked.load();
  return made;
}

template <class Tag>
Made run_surface(const SurfaceMesh& surface, double feature_angle, const std::vector<Polyline>& lines,
                 const Sizing& sizing, double edge_size, double cell_size, double facet_size, double facet_distance,
                 double edge_factor, double cell_factor, double facet_factor, double distance_factor, double angle,
                 double ratio, const Sliver& sliver, int seed) {
  using Tr = typename CGAL::Mesh_triangulation_3<SurfaceDomain, CGAL::Default, Tag>::type;
  using C3t3 = CGAL::Mesh_complex_3_in_triangulation_3<Tr, SurfaceDomain::Corner_index, SurfaceDomain::Curve_index>;
  using Criteria = CGAL::Mesh_criteria_3<Tr>;
  using Index = SurfaceDomain::Index;

  CGAL::get_default_random() = CGAL::Random(seed);
  SurfaceDomain domain(surface);
  // Every edge sharper than the angle kept - or, at 0 or less, only the lines given.
  if (feature_angle > 0) domain.detect_features(feature_angle);
  if (!lines.empty()) domain.add_features(lines.begin(), lines.end());
  Criteria criteria(params::edge_size(sizing.of<Index>(edge_size, edge_factor))
                        .facet_angle(angle)
                        .facet_size(sizing.of<Index>(facet_size, facet_factor))
                        .facet_distance(sizing.of<Index>(facet_distance, distance_factor))
                        .cell_radius_edge_ratio(ratio)
                        .cell_size(sizing.of<Index>(cell_size, cell_factor)));
  return generate<C3t3>(domain, criteria, sliver);
}

// Runs `work` sequentially, or on `threads` TBB threads with the parallel mesher, without the GIL.
template <class Sequential, class Parallel>
Made on_threads(int threads, Sequential sequential, Parallel parallel) {
  py::gil_scoped_release released;
  if (threads > 1) {
#ifdef CGAL_LINKED_WITH_TBB
    tbb::global_control limit(tbb::global_control::max_allowed_parallelism, std::size_t(threads));
    return parallel();
#else
    throw std::runtime_error("built without TBB: threads must be 1");
#endif
  }
  return sequential();
}

py::dict to_python(const Made& made) {
  const py::ssize_t n = py::ssize_t(made.xyz.size() / 3), m = py::ssize_t(made.tets.size() / 4);
  py::array_t<double> nodes({n, py::ssize_t(3)});
  py::array_t<std::int64_t> tets({m, py::ssize_t(4)});
  std::memcpy(nodes.mutable_data(), made.xyz.data(), made.xyz.size() * sizeof(double));
  std::memcpy(tets.mutable_data(), made.tets.data(), made.tets.size() * sizeof(std::int64_t));
  py::dict out;
  out["nodes"] = nodes;
  out["tets"] = tets;
  out["refine_s"] = made.refine;
  out["perturb_s"] = made.perturb;
  out["exude_s"] = made.exude;
  out["field_queries"] = made.asked;
  return out;
}

std::vector<Polyline> polylines_of(const std::vector<Doubles>& lines) {
  std::vector<Polyline> polylines;
  for (const auto& line : lines) {
    if (line.ndim() != 2 || line.shape(1) != 3 || line.shape(0) < 2)
      throw std::invalid_argument("a line is an (n, 3) array of at least two points");
    Polyline points;
    for (py::ssize_t i = 0; i < line.shape(0); ++i) points.emplace_back(line.at(i, 0), line.at(i, 1), line.at(i, 2));
    polylines.push_back(std::move(points));
  }
  return polylines;
}

py::dict mesh(const Floats& sdf, std::array<double, 3> origin, double spacing, double outside, double cell_size,
              double facet_size, double facet_distance, std::optional<Floats> sizes, std::array<double, 3> size_origin,
              double size_spacing, double cell_factor, double facet_factor, double distance_factor, double facet_angle,
              double radius_edge_ratio, double error_bound, bool perturb, bool exude, double sliver_bound,
              double time_limit, int threads, int seed, const std::vector<Doubles>& lines, double edge_size,
              double edge_factor) {
  const Grid field = grid_of(sdf, origin, spacing, outside, false);
  const Sizing sizing = sizing_of(sizes, size_origin, size_spacing);
  const Sliver sliver{perturb, exude, sliver_bound, time_limit};
  const std::vector<Polyline> polylines = polylines_of(lines);
  auto with = [&](auto tag) {
    return [&, tag] {
      if (!polylines.empty())
        return run_edged_field<decltype(tag)>(field, polylines, sizing, edge_size, cell_size, facet_size,
                                              facet_distance, edge_factor, cell_factor, facet_factor, distance_factor,
                                              facet_angle, radius_edge_ratio, error_bound, sliver, seed);
      return run_field<decltype(tag)>(field, sizing, cell_size, facet_size, facet_distance, cell_factor, facet_factor,
                                      distance_factor, facet_angle, radius_edge_ratio, error_bound, sliver, seed);
    };
  };
  return to_python(on_threads(threads, with(CGAL::Sequential_tag()), with(CGAL::Parallel_tag())));
}

py::dict mesh_surface(const Doubles& vertices, const Indices& triangles, double feature_angle, double edge_size,
                      double cell_size, double facet_size, double facet_distance, std::optional<Floats> sizes,
                      std::array<double, 3> size_origin, double size_spacing, double edge_factor, double cell_factor,
                      double facet_factor, double distance_factor, double facet_angle, double radius_edge_ratio,
                      bool perturb, bool exude, double sliver_bound, double time_limit, int threads, int seed,
                      const std::vector<Doubles>& lines) {
  if (vertices.ndim() != 2 || vertices.shape(1) != 3 || triangles.ndim() != 2 || triangles.shape(1) != 3)
    throw std::invalid_argument("vertices are (n, 3) and triangles (m, 3)");
  std::vector<Point> points;
  points.reserve(vertices.shape(0));
  for (py::ssize_t i = 0; i < vertices.shape(0); ++i)
    points.emplace_back(vertices.at(i, 0), vertices.at(i, 1), vertices.at(i, 2));
  std::vector<std::array<std::size_t, 3>> faces;
  faces.reserve(triangles.shape(0));
  for (py::ssize_t i = 0; i < triangles.shape(0); ++i)
    faces.push_back({std::size_t(triangles.at(i, 0)), std::size_t(triangles.at(i, 1)), std::size_t(triangles.at(i, 2))});
  // Where two sheets touch at a vertex the soup is no polygon mesh; orienting it splits such vertices.
  namespace pmp = CGAL::Polygon_mesh_processing;
  const std::size_t given = points.size();
  if (!pmp::is_polygon_soup_a_polygon_mesh(faces)) pmp::orient_polygon_soup(points, faces);
  SurfaceMesh surface;
  pmp::polygon_soup_to_polygon_mesh(points, faces, surface);
  if (!CGAL::is_closed(surface)) {
    std::size_t border = 0;
    for (auto h : surface.halfedges()) border += surface.is_border(h) ? 1 : 0;
    throw std::invalid_argument("the surface is not closed: " + std::to_string(border) + " border edges, " +
                                std::to_string(points.size() - given) + " vertices split");
  }

  const Sizing sizing = sizing_of(sizes, size_origin, size_spacing);
  const Sliver sliver{perturb, exude, sliver_bound, time_limit};
  const std::vector<Polyline> polylines = polylines_of(lines);
  auto with = [&](auto tag) {
    return [&, tag] {
      return run_surface<decltype(tag)>(surface, feature_angle, polylines, sizing, edge_size, cell_size, facet_size,
                                        facet_distance, edge_factor, cell_factor, facet_factor, distance_factor,
                                        facet_angle, radius_edge_ratio, sliver, seed);
    };
  };
  return to_python(on_threads(threads, with(CGAL::Sequential_tag()), with(CGAL::Parallel_tag())));
}

PYBIND11_MODULE(cgal_field, m) {
  m.doc() = "CGAL Mesh_3 on a signed distance field sampled on a grid, or on a closed triangulated surface.";
  m.def("mesh", &mesh, py::arg("sdf"), py::arg("origin"), py::arg("spacing"), py::arg("outside"),
        py::arg("cell_size") = 40.0, py::arg("facet_size") = 30.0, py::arg("facet_distance") = 2.0,
        py::arg("sizes") = py::none(), py::arg("size_origin") = std::array<double, 3>{0, 0, 0},
        py::arg("size_spacing") = 1.0, py::arg("cell_factor") = 0.0, py::arg("facet_factor") = 0.0,
        py::arg("distance_factor") = 0.0, py::arg("facet_angle") = 25.0, py::arg("radius_edge_ratio") = 2.0,
        py::arg("error_bound") = 5e-6, py::arg("perturb") = true, py::arg("exude") = true,
        py::arg("sliver_bound") = 0.0, py::arg("time_limit") = 0.0, py::arg("threads") = 1, py::arg("seed") = 0,
        py::arg("lines") = std::vector<Doubles>{}, py::arg("edge_size") = 20.0, py::arg("edge_factor") = 0.0,
        "Linear tets of the part the signed distance `sdf` (negative inside; C order, origin, spacing) holds.\n"
        "Criteria are constants, or factors of the element-size grid `sizes` where a factor is given.\n"
        "Slivers are perturbed and exuded until every dihedral angle is above `sliver_bound` degrees\n"
        "(0: while a step helps), each for at most `time_limit` seconds (0: no limit).\n"
        "`lines` are polylines the mesh follows - a closed one repeats its first point last - with vertices\n"
        "at most `edge_size` apart (or `edge_factor` times the size grid).\n"
        "Returns nodes, tets, the seconds refining, perturbing and exuding, and the field questions asked.");
  m.def("mesh_surface", &mesh_surface, py::arg("vertices"), py::arg("triangles"), py::arg("feature_angle") = 60.0,
        py::arg("edge_size") = 20.0, py::arg("cell_size") = 40.0, py::arg("facet_size") = 30.0,
        py::arg("facet_distance") = 2.0, py::arg("sizes") = py::none(),
        py::arg("size_origin") = std::array<double, 3>{0, 0, 0}, py::arg("size_spacing") = 1.0,
        py::arg("edge_factor") = 0.0, py::arg("cell_factor") = 0.0, py::arg("facet_factor") = 0.0,
        py::arg("distance_factor") = 0.0, py::arg("facet_angle") = 25.0, py::arg("radius_edge_ratio") = 2.0,
        py::arg("perturb") = true, py::arg("exude") = true, py::arg("sliver_bound") = 0.0,
        py::arg("time_limit") = 0.0, py::arg("threads") = 1, py::arg("seed") = 0,
        py::arg("lines") = std::vector<Doubles>{},
        "Linear tets of the part a closed triangulated surface bounds, its edges sharper than `feature_angle`\n"
        "degrees kept (none at 0 or less) and the polylines `lines` followed; criteria as for `mesh`, plus\n"
        "`edge_size` along the kept edges and lines.");
}
