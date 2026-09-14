/**
 * A finite-element view: the outside of a mesh with its element edges, the patches the deck's
 * groups cover, the supports, couplings and loads drawn where the deck applies them, and a result
 * as banded contours - optionally on the deformed shape.
 *
 * Raw WebGL2, like the CAD view. Triangles are drawn unindexed, three vertices each, so a
 * triangle's group colours it flat and its element edges come from barycentric coordinates in the
 * fragment shader - no second pass for the wireframe. Picking renders ids into an offscreen buffer
 * and reads one pixel: a patch's group, or a glyph.
 *
 * Two views can share one camera object, which is all a split view needs.
 */

export interface Skin {
  positions: Float32Array; // 3 per vertex
  triangles: Uint32Array; // 3 per triangle
  groups: Uint16Array; // per triangle, 0xffff for none
  nodes: Uint32Array; // mesh node of each vertex
  groupNames: string[];
}

export interface GlyphData {
  held: { group: string; points: number[][]; count: number; dofs: Record<string, number>; active: boolean }[];
  rigid: { groups: string[]; reference: string | null; point: number[] | null; spokes: number[][]; count: number }[];
  distributing: { group: string; reference: string; point: number[]; spokes: number[][]; count: number }[];
  loads: { group: string; point: number[]; force: number[]; moment: number[]; nodes: number }[];
  scale: { span: number; force_max: number; moment_max: number };
}

export interface Pick {
  kind: "group" | "glyph";
  index: number;
}

export interface GlyphLabel {
  kind: "support" | "rigid" | "distributing" | "force" | "moment";
  name: string;
  detail: string;
}

export interface Camera {
  target: [number, number, number];
  distance: number;
  azimuth: number;
  elevation: number;
  fovY: number;
  near: number;
  far: number;
  extent: number;
}

export type ColourMode = "patches" | "contour" | "difference" | "plain";

/** agenticCAE's colours: free surface, bore patch, bolt patch, spokes, supports, X / Y / Z. */
export const FE_COLOURS = {
  surface: [154, 162, 170],
  plain: [173, 183, 194],
  distributing: [42, 118, 175],
  rigid: [214, 150, 40],
  spokes: [120, 74, 160],
  support: [38, 44, 54],
  x: [200, 67, 58],
  y: [47, 143, 69],
  z: [34, 102, 204],
  hover: [15, 61, 145],
};

/** agenticCAE's contour stops, pale blue to red. */
export const CONTOUR_STOPS: [number, number, number][] = [
  [222, 235, 246],
  [126, 181, 219],
  [86, 170, 158],
  [158, 198, 92],
  [240, 176, 52],
  [206, 62, 44],
];
/** A diverging scale for differences: blue below, white at nothing, red above. */
export const DIFFERENCE_STOPS: [number, number, number][] = [
  [43, 91, 168],
  [146, 180, 222],
  [247, 247, 247],
  [236, 158, 122],
  [178, 42, 38],
];

const SURFACE_VS = `#version 300 es
layout(location = 0) in vec3 a_position;
layout(location = 1) in float a_value;
layout(location = 2) in uint a_group;
layout(location = 3) in vec3 a_offset;
uniform mat4 u_viewProjection;
uniform float u_deform;
out vec3 v_world;
out float v_value;
flat out uint v_group;
out vec3 v_bary;
void main() {
  vec3 p = a_position + u_deform * a_offset;
  v_world = p;
  v_value = a_value;
  v_group = a_group;
  int corner = gl_VertexID % 3;
  v_bary = corner == 0 ? vec3(1, 0, 0) : corner == 1 ? vec3(0, 1, 0) : vec3(0, 0, 1);
  gl_Position = u_viewProjection * vec4(p, 1.0);
}`;

const SURFACE_FS = `#version 300 es
precision highp float;
precision highp int;
in vec3 v_world;
in float v_value;
flat in uint v_group;
in vec3 v_bary;
uniform vec3 u_eye;
uniform int u_mode;         // 0 patches, 1 contour, 2 difference, 3 plain
uniform int u_edges;
uniform vec2 u_range;
uniform float u_bands;
uniform vec3 u_stops[6];
uniform int u_stopCount;
uniform sampler2D u_groupColours;
uniform int u_hovered;
uniform vec3 u_surface;
uniform vec3 u_plain;
out vec4 outColour;

vec3 ramp(float t) {
  float x = clamp(t, 0.0, 1.0) * float(u_stopCount - 1);
  int i = int(floor(x));
  if (i >= u_stopCount - 1) return u_stops[u_stopCount - 1];
  return mix(u_stops[i], u_stops[i + 1], x - float(i));
}

void main() {
  vec3 n = normalize(cross(dFdx(v_world), dFdy(v_world)));
  vec3 view = normalize(u_eye - v_world);
  if (dot(n, view) < 0.0) n = -n;
  float key = 0.62 + 0.40 * max(dot(n, normalize(vec3(0.35, 0.45, 0.82))), 0.0);
  float fill = 0.14 * max(dot(n, normalize(vec3(-0.5, -0.3, -0.4))), 0.0);
  float grazing = 1.0 - 0.30 * pow(1.0 - max(dot(n, view), 0.0), 2.0);
  vec3 base = u_surface;
  if (u_mode == 3) {
    base = u_plain;
  } else if (u_mode == 0) {
    if (v_group != 65535u) {
      vec4 c = texelFetch(u_groupColours, ivec2(int(v_group) % 1024, int(v_group) / 1024), 0);
      if (c.a > 0.0) base = c.rgb;
    }
  } else {
    if (isnan(v_value)) {
      base = vec3(0.55, 0.57, 0.58);
    } else {
      float t = (v_value - u_range.x) / max(u_range.y - u_range.x, 1e-30);
      t = clamp(t, 0.0, 0.99999);
      float band = (floor(t * u_bands) + 0.5) / u_bands;
      base = ramp(band);
    }
  }
  if (u_hovered >= 0 && int(v_group) == u_hovered && v_group != 65535u) {
    base = mix(base, vec3(0.059, 0.239, 0.569), 0.45);
  }
  vec3 colour = base * (key + fill) * grazing;
  if (u_edges == 1) {
    vec3 d = fwidth(v_bary);
    vec3 a = smoothstep(vec3(0.0), d * 1.1, v_bary);
    float edge = 1.0 - min(min(a.x, a.y), a.z);
    colour = mix(colour, vec3(0.10, 0.12, 0.16), edge * 0.55);
  }
  outColour = vec4(colour, 1.0);
}`;

const PICK_VS = `#version 300 es
layout(location = 0) in vec3 a_position;
layout(location = 2) in uint a_id;
layout(location = 3) in vec3 a_offset;
uniform mat4 u_viewProjection;
uniform float u_deform;
flat out uint v_id;
void main() {
  v_id = a_id;
  gl_Position = u_viewProjection * vec4(a_position + u_deform * a_offset, 1.0);
}`;

const PICK_FS = `#version 300 es
precision highp float;
precision highp int;
flat in uint v_id;
uniform uint u_base;
out vec4 outColour;
void main() {
  uint id = v_id == 65535u && u_base == 1u ? 0u : v_id + u_base;
  outColour = vec4(float(id & 255u), float((id >> 8) & 255u), float((id >> 16) & 255u), 255.0) / 255.0;
}`;

const GLYPH_VS = `#version 300 es
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_colour;
layout(location = 2) in uint a_id;
uniform mat4 u_viewProjection;
out vec3 v_world;
out vec3 v_colour;
flat out uint v_id;
void main() {
  v_world = a_position;
  v_colour = a_colour;
  v_id = a_id;
  gl_Position = u_viewProjection * vec4(a_position, 1.0);
}`;

const GLYPH_FS = `#version 300 es
precision highp float;
precision highp int;
in vec3 v_world;
in vec3 v_colour;
flat in uint v_id;
uniform vec3 u_eye;
uniform int u_lit;
uniform int u_hovered;
out vec4 outColour;
void main() {
  vec3 colour = v_colour;
  if (u_lit == 1) {
    vec3 n = normalize(cross(dFdx(v_world), dFdy(v_world)));
    vec3 view = normalize(u_eye - v_world);
    if (dot(n, view) < 0.0) n = -n;
    colour *= 0.55 + 0.55 * max(dot(n, normalize(vec3(0.35, 0.45, 0.82))), 0.0);
  }
  if (u_hovered >= 0 && int(v_id) == u_hovered) colour = mix(colour, vec3(1.0), 0.35);
  outColour = vec4(colour, 1.0);
}`;

const NO_GROUP = 0xffff;
const GLYPH_BASE = 0x10000;

export class FeRenderer {
  private gl: WebGL2RenderingContext;
  private surface: WebGLProgram;
  private pickProgram: WebGLProgram;
  private glyphProgram: WebGLProgram;
  private vao: WebGLVertexArrayObject | null = null;
  private buffers: Record<string, WebGLBuffer> = {};
  private vertexCount = 0;
  private skin: Skin | null = null;
  private groupTexture: WebGLTexture;
  private glyphVao: WebGLVertexArrayObject | null = null;
  private glyphBuffers: WebGLBuffer[] = [];
  private glyphTriangles = 0;
  private lineVao: WebGLVertexArrayObject | null = null;
  private lineBuffers: WebGLBuffer[] = [];
  private lineCount = 0;
  private pickFramebuffer: WebGLFramebuffer;
  private pickTexture: WebGLTexture;
  private pickDepth: WebGLRenderbuffer;
  private pickSize = { width: 0, height: 0 };

  labels: GlyphLabel[] = [];
  mode: ColourMode = "patches";
  edges = true;
  showGlyphs = true;
  range: [number, number] = [0, 1];
  bands = 48;
  deform = 0;
  hoveredGroup = -1;
  hoveredGlyph = -1;
  stops: [number, number, number][] = CONTOUR_STOPS;

  constructor(
    private canvas: HTMLCanvasElement,
    public camera: Camera,
  ) {
    const gl = canvas.getContext("webgl2", { antialias: true, depth: true, preserveDrawingBuffer: true });
    if (!gl) throw new Error("WebGL2 is not available in this browser");
    this.gl = gl;
    this.surface = link(gl, SURFACE_VS, SURFACE_FS);
    this.pickProgram = link(gl, PICK_VS, PICK_FS);
    this.glyphProgram = link(gl, GLYPH_VS, GLYPH_FS);
    this.groupTexture = gl.createTexture()!;
    this.pickFramebuffer = gl.createFramebuffer()!;
    this.pickTexture = gl.createTexture()!;
    this.pickDepth = gl.createRenderbuffer()!;
    gl.enable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
  }

  /** The mesh's outside. Replaces whatever was there; values and offsets start empty. */
  setSkin(skin: Skin | null): void {
    const gl = this.gl;
    for (const b of Object.values(this.buffers)) gl.deleteBuffer(b);
    this.buffers = {};
    if (this.vao) gl.deleteVertexArray(this.vao);
    this.vao = null;
    this.skin = skin;
    if (!skin) {
      this.vertexCount = 0;
      return;
    }
    const t = skin.triangles;
    const count = t.length;
    const positions = new Float32Array(count * 3);
    const groups = new Uint32Array(count);
    for (let i = 0; i < count; i++) {
      const v = t[i];
      positions[i * 3] = skin.positions[v * 3];
      positions[i * 3 + 1] = skin.positions[v * 3 + 1];
      positions[i * 3 + 2] = skin.positions[v * 3 + 2];
      groups[i] = skin.groups[Math.floor(i / 3)];
    }
    this.vertexCount = count;
    this.vao = gl.createVertexArray()!;
    gl.bindVertexArray(this.vao);
    this.buffers.position = buffer(gl, positions);
    attribute(gl, this.buffers.position, 0, 3);
    this.buffers.value = buffer(gl, new Float32Array(count));
    attribute(gl, this.buffers.value, 1, 1);
    this.buffers.group = buffer(gl, groups);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.group);
    gl.enableVertexAttribArray(2);
    gl.vertexAttribIPointer(2, 1, gl.UNSIGNED_INT, 0, 0);
    this.buffers.offset = buffer(gl, new Float32Array(count * 3));
    attribute(gl, this.buffers.offset, 3, 3);
    gl.bindVertexArray(null);
  }

  /** One value per skin vertex, and optionally a displacement per vertex for the deformed shape. */
  setValues(values: Float32Array | null, vectors: Float32Array | null = null): void {
    const gl = this.gl;
    const skin = this.skin;
    if (!skin || !this.vao) return;
    const t = skin.triangles;
    const expanded = new Float32Array(t.length);
    if (values) for (let i = 0; i < t.length; i++) expanded[i] = values[t[i]];
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.value);
    gl.bufferData(gl.ARRAY_BUFFER, expanded, gl.DYNAMIC_DRAW);
    const offsets = new Float32Array(t.length * 3);
    if (vectors) {
      for (let i = 0; i < t.length; i++) {
        const v = t[i];
        offsets[i * 3] = vectors[v * 3];
        offsets[i * 3 + 1] = vectors[v * 3 + 1];
        offsets[i * 3 + 2] = vectors[v * 3 + 2];
      }
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.offset);
    gl.bufferData(gl.ARRAY_BUFFER, offsets, gl.DYNAMIC_DRAW);
  }

  /** The colour of each group's patch, by group index; a group not given is left as surface. */
  setGroupColours(colours: ([number, number, number] | null)[]): void {
    const gl = this.gl;
    const width = 1024;
    const rows = Math.max(1, Math.ceil(colours.length / width));
    const data = new Uint8Array(width * rows * 4);
    colours.forEach((c, i) => {
      if (!c) return;
      data.set([c[0], c[1], c[2], 255], i * 4);
    });
    gl.bindTexture(gl.TEXTURE_2D, this.groupTexture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, width, rows, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
  }

  /** Supports, couplings and loads, built as geometry in the part's frame. */
  setGlyphs(glyphs: GlyphData | null): void {
    const gl = this.gl;
    for (const b of [...this.glyphBuffers, ...this.lineBuffers]) gl.deleteBuffer(b);
    this.glyphBuffers = [];
    this.lineBuffers = [];
    if (this.glyphVao) gl.deleteVertexArray(this.glyphVao);
    if (this.lineVao) gl.deleteVertexArray(this.lineVao);
    this.glyphVao = null;
    this.lineVao = null;
    this.glyphTriangles = 0;
    this.lineCount = 0;
    this.labels = [];
    if (!glyphs) return;
    const built = buildGlyphs(glyphs);
    this.labels = built.labels;
    const make = (positions: number[], colours: number[], ids: number[]) => {
      const vao = gl.createVertexArray()!;
      gl.bindVertexArray(vao);
      const p = buffer(gl, new Float32Array(positions));
      attribute(gl, p, 0, 3);
      const c = buffer(gl, new Float32Array(colours));
      attribute(gl, c, 1, 3);
      const idb = buffer(gl, new Uint32Array(ids));
      gl.bindBuffer(gl.ARRAY_BUFFER, idb);
      gl.enableVertexAttribArray(2);
      gl.vertexAttribIPointer(2, 1, gl.UNSIGNED_INT, 0, 0);
      gl.bindVertexArray(null);
      return { vao, buffers: [p, c, idb] };
    };
    const tri = make(built.triangles, built.triangleColours, built.triangleIds);
    this.glyphVao = tri.vao;
    this.glyphBuffers = tri.buffers;
    this.glyphTriangles = built.triangles.length / 3;
    const line = make(built.lines, built.lineColours, built.lineIds);
    this.lineVao = line.vao;
    this.lineBuffers = line.buffers;
    this.lineCount = built.lines.length / 3;
  }

  frame(bbox: number[]): void {
    const [x0, y0, z0, x1, y1, z1] = bbox;
    this.camera.target = [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2];
    const extent = Math.max(x1 - x0, y1 - y0, z1 - z0);
    this.camera.extent = extent;
    this.camera.distance = extent * 1.7;
    this.camera.far = extent * 12;
    this.camera.near = extent / 500;
  }

  render(): void {
    const gl = this.gl;
    const { width, height } = this.resize();
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, width, height);
    gl.clearColor(0.976, 0.98, 0.988, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const vp = this.viewProjection(width / Math.max(height, 1));
    const eye = this.eye();
    if (this.vao && this.vertexCount) {
      const p = this.surface;
      gl.useProgram(p);
      gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_viewProjection"), false, vp);
      gl.uniform3fv(gl.getUniformLocation(p, "u_eye"), eye);
      gl.uniform1f(gl.getUniformLocation(p, "u_deform"), this.deform);
      gl.uniform1i(gl.getUniformLocation(p, "u_mode"), { patches: 0, contour: 1, difference: 2, plain: 3 }[this.mode]);
      gl.uniform1i(gl.getUniformLocation(p, "u_edges"), this.edges ? 1 : 0);
      gl.uniform2f(gl.getUniformLocation(p, "u_range"), this.range[0], this.range[1]);
      gl.uniform1f(gl.getUniformLocation(p, "u_bands"), this.bands);
      const stops = this.mode === "difference" ? DIFFERENCE_STOPS : this.stops;
      const flat = new Float32Array(18);
      stops.slice(0, 6).forEach((s, i) => flat.set([s[0] / 255, s[1] / 255, s[2] / 255], i * 3));
      gl.uniform3fv(gl.getUniformLocation(p, "u_stops"), flat);
      gl.uniform1i(gl.getUniformLocation(p, "u_stopCount"), Math.min(stops.length, 6));
      gl.uniform1i(gl.getUniformLocation(p, "u_hovered"), this.hoveredGroup);
      gl.uniform3fv(gl.getUniformLocation(p, "u_surface"), FE_COLOURS.surface.map((c) => c / 255));
      gl.uniform3fv(gl.getUniformLocation(p, "u_plain"), FE_COLOURS.plain.map((c) => c / 255));
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.groupTexture);
      gl.uniform1i(gl.getUniformLocation(p, "u_groupColours"), 0);
      gl.bindVertexArray(this.vao);
      gl.drawArrays(gl.TRIANGLES, 0, this.vertexCount);
    }
    if (this.showGlyphs && this.deform === 0) this.drawGlyphs(vp, eye);
    gl.bindVertexArray(null);
  }

  private drawGlyphs(vp: Float32Array, eye: Float32Array): void {
    const gl = this.gl;
    const p = this.glyphProgram;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_viewProjection"), false, vp);
    gl.uniform3fv(gl.getUniformLocation(p, "u_eye"), eye);
    gl.uniform1i(gl.getUniformLocation(p, "u_hovered"), this.hoveredGlyph);
    if (this.glyphVao && this.glyphTriangles) {
      gl.uniform1i(gl.getUniformLocation(p, "u_lit"), 1);
      gl.bindVertexArray(this.glyphVao);
      gl.drawArrays(gl.TRIANGLES, 0, this.glyphTriangles);
    }
    if (this.lineVao && this.lineCount) {
      gl.uniform1i(gl.getUniformLocation(p, "u_lit"), 0);
      gl.bindVertexArray(this.lineVao);
      gl.drawArrays(gl.LINES, 0, this.lineCount);
    }
  }

  /** What is under a pixel of the canvas (in CSS pixels): a patch's group, a glyph, or nothing. */
  pick(cssX: number, cssY: number): Pick | null {
    const gl = this.gl;
    const rect = this.canvas.getBoundingClientRect();
    const scale = 0.5 * (this.canvas.width / Math.max(rect.width, 1));
    const width = Math.max(1, Math.floor(this.canvas.width / 2));
    const height = Math.max(1, Math.floor(this.canvas.height / 2));
    this.ensurePick(width, height);
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickFramebuffer);
    gl.viewport(0, 0, width, height);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const vp = this.viewProjection(width / height);
    const p = this.pickProgram;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_viewProjection"), false, vp);
    if (this.vao && this.vertexCount) {
      gl.uniform1f(gl.getUniformLocation(p, "u_deform"), this.deform);
      gl.uniform1ui(gl.getUniformLocation(p, "u_base"), 1);
      gl.bindVertexArray(this.vao);
      gl.drawArrays(gl.TRIANGLES, 0, this.vertexCount);
    }
    if (this.showGlyphs && this.deform === 0 && this.glyphVao) {
      gl.uniform1f(gl.getUniformLocation(p, "u_deform"), 0);
      gl.uniform1ui(gl.getUniformLocation(p, "u_base"), GLYPH_BASE + 1);
      gl.bindVertexArray(this.glyphVao);
      gl.drawArrays(gl.TRIANGLES, 0, this.glyphTriangles);
      if (this.lineVao) {
        gl.bindVertexArray(this.lineVao);
        gl.drawArrays(gl.LINES, 0, this.lineCount);
      }
    }
    gl.bindVertexArray(null);
    const x = Math.round(cssX * scale);
    const y = Math.round(height - cssY * scale);
    const pixel = new Uint8Array(4);
    if (x >= 0 && y >= 0 && x < width && y < height) gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    const id = pixel[0] | (pixel[1] << 8) | (pixel[2] << 16);
    if (id === 0) return null;
    if (id > GLYPH_BASE) return { kind: "glyph", index: id - GLYPH_BASE - 1 };
    const group = id - 1;
    return group === NO_GROUP ? null : { kind: "group", index: group };
  }

  orbit(dx: number, dy: number): void {
    this.camera.azimuth -= dx * 0.008;
    this.camera.elevation = Math.min(Math.max(this.camera.elevation + dy * 0.008, -1.5), 1.5);
  }

  pan(dx: number, dy: number): void {
    const scale = this.camera.distance * 0.0013;
    const [right, up] = this.basis();
    for (let i = 0; i < 3; i++) this.camera.target[i] += (-right[i] * dx + up[i] * dy) * scale;
  }

  zoom(delta: number): void {
    const extent = this.camera.extent || 1000;
    this.camera.distance = Math.min(Math.max(this.camera.distance * Math.exp(delta * 0.0012), extent * 0.02), extent * 20);
  }

  snapshot(): string {
    return this.canvas.toDataURL("image/png");
  }

  dispose(): void {
    const gl = this.gl;
    this.setSkin(null);
    this.setGlyphs(null);
    gl.deleteTexture(this.groupTexture);
    gl.deleteTexture(this.pickTexture);
    gl.deleteRenderbuffer(this.pickDepth);
    gl.deleteFramebuffer(this.pickFramebuffer);
    gl.deleteProgram(this.surface);
    gl.deleteProgram(this.pickProgram);
    gl.deleteProgram(this.glyphProgram);
  }

  private ensurePick(width: number, height: number): void {
    if (this.pickSize.width === width && this.pickSize.height === height) return;
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, this.pickTexture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.bindRenderbuffer(gl.RENDERBUFFER, this.pickDepth);
    gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT24, width, height);
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickFramebuffer);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.pickTexture, 0);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, this.pickDepth);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    this.pickSize = { width, height };
  }

  private resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.canvas.clientWidth * ratio));
    const height = Math.max(1, Math.floor(this.canvas.clientHeight * ratio));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    return { width, height };
  }

  private eye(): Float32Array {
    const { target, distance, azimuth, elevation } = this.camera;
    const c = Math.cos(elevation);
    return new Float32Array([
      target[0] + distance * c * Math.cos(azimuth),
      target[1] + distance * c * Math.sin(azimuth),
      target[2] + distance * Math.sin(elevation),
    ]);
  }

  private basis(): [number[], number[]] {
    const { azimuth, elevation } = this.camera;
    const forward = [-Math.cos(elevation) * Math.cos(azimuth), -Math.cos(elevation) * Math.sin(azimuth), -Math.sin(elevation)];
    const right = normalise(cross(forward, [0, 0, 1]));
    return [right, normalise(cross(right, forward))];
  }

  private viewProjection(aspect: number): Float32Array {
    const e = this.eye();
    const view = lookAt([e[0], e[1], e[2]], this.camera.target, [0, 0, 1]);
    return multiply(perspective(this.camera.fovY, aspect, this.camera.near, this.camera.far), view);
  }
}

export function newCamera(): Camera {
  // agenticCAE looks at the housing from below, so the ribs and bores on its underside show.
  return { target: [0, 0, 0], distance: 3000, azimuth: -0.95, elevation: -0.55, fovY: 0.7, near: 1, far: 20000, extent: 1000 };
}

// --- glyph geometry -----------------------------------------------------------------------------

interface Built {
  triangles: number[];
  triangleColours: number[];
  triangleIds: number[];
  lines: number[];
  lineColours: number[];
  lineIds: number[];
  labels: GlyphLabel[];
}

function buildGlyphs(g: GlyphData): Built {
  const out: Built = { triangles: [], triangleColours: [], triangleIds: [], lines: [], lineColours: [], lineIds: [], labels: [] };
  const span = g.scale.span || 1000;
  const colour = (c: number[]) => [c[0] / 255, c[1] / 255, c[2] / 255];
  const label = (l: GlyphLabel) => out.labels.push(l) - 1;
  const tri = (a: number[], b: number[], c: number[], col: number[], id: number) => {
    out.triangles.push(...a, ...b, ...c);
    out.triangleColours.push(...col, ...col, ...col);
    out.triangleIds.push(id, id, id);
  };
  const line = (a: number[], b: number[], col: number[], id: number) => {
    out.lines.push(...a, ...b);
    out.lineColours.push(...col, ...col);
    out.lineIds.push(id, id);
  };

  for (const r of g.rigid) {
    if (!r.point) continue;
    const id = label({ kind: "rigid", name: r.groups.filter((x) => x !== r.reference).join(", "), detail: `rigid to ${r.reference} · ${r.count} nodes` });
    for (const s of r.spokes) line(r.point, s, colour(FE_COLOURS.rigid), id);
  }
  for (const d of g.distributing) {
    const id = label({ kind: "distributing", name: d.group, detail: `distributing to ${d.reference} · ${d.count} nodes` });
    for (const s of d.spokes) line(d.point, s, colour(FE_COLOURS.spokes), id);
  }
  for (const h of g.held) {
    const dofs = Object.entries(h.dofs).map(([k, v]) => `${k} = ${v}`).join(", ");
    const id = label({ kind: "support", name: h.group, detail: `held: ${dofs}${h.count > 1 ? ` · ${h.count} nodes` : ""}` });
    const height = span * 0.028;
    const width = span * 0.012;
    for (const p of h.points.slice(0, h.count > 1 ? 24 : 1)) pyramid(p, height, width, colour(FE_COLOURS.support), id, tri);
  }
  const axes = [colour(FE_COLOURS.x), colour(FE_COLOURS.y), colour(FE_COLOURS.z)];
  const names = ["X", "Y", "Z"];
  for (const load of g.loads) {
    for (let c = 0; c < 3; c++) {
      const f = load.force[c];
      if (f) {
        const length = span * Math.max(0.03, (0.28 * Math.abs(f)) / (g.scale.force_max || 1));
        const dir = [0, 0, 0];
        dir[c] = Math.sign(f);
        const id = label({ kind: "force", name: load.group, detail: `F${names[c].toLowerCase()} ${formatForce(f)}` });
        arrow(load.point, dir, length, span * 0.008, axes[c], id, tri);
      }
      const m = load.moment[c];
      if (m) {
        const radius = span * Math.max(0.025, (0.085 * Math.abs(m)) / (g.scale.moment_max || 1));
        const id = label({ kind: "moment", name: load.group, detail: `M${names[c].toLowerCase()} ${m.toExponential(3)}` });
        arc(load.point, c, Math.sign(m), radius, span * 0.004, axes[c], id, tri);
      }
    }
  }
  return out;
}

function formatForce(f: number): string {
  return `${f.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

type Tri = (a: number[], b: number[], c: number[], col: number[], id: number) => void;

function frameOf(dir: number[]): [number[], number[]] {
  const helper = Math.abs(dir[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
  const u = normalise(cross(dir, helper));
  return [u, cross(dir, u)];
}

/** A shaft and a cone, the tip at ``tip``, pointing along ``dir``. */
function arrow(tip: number[], dir: number[], length: number, radius: number, col: number[], id: number, tri: Tri) {
  const [u, v] = frameOf(dir);
  const head = length * 0.32;
  const base = tip.map((t, i) => t - dir[i] * length);
  const neck = tip.map((t, i) => t - dir[i] * head);
  const sides = 10;
  const ring = (centre: number[], r: number, k: number) => {
    const a = (2 * Math.PI * k) / sides;
    return centre.map((c, i) => c + r * (Math.cos(a) * u[i] + Math.sin(a) * v[i]));
  };
  for (let k = 0; k < sides; k++) {
    const a0 = ring(base, radius, k);
    const a1 = ring(base, radius, k + 1);
    const b0 = ring(neck, radius, k);
    const b1 = ring(neck, radius, k + 1);
    tri(a0, a1, b1, col, id);
    tri(a0, b1, b0, col, id);
    const c0 = ring(neck, radius * 2.4, k);
    const c1 = ring(neck, radius * 2.4, k + 1);
    tri(c0, c1, tip, col, id);
    tri(c0, c1, neck, col, id);
  }
}

/** A 280° arc round ``axis`` through ``centre``, right-handed with the moment's sign, one head. */
function arc(centre: number[], axis: number, sign: number, radius: number, tube: number, col: number[], id: number, tri: Tri) {
  const dir = [0, 0, 0];
  dir[axis] = 1;
  const [u, v] = frameOf(dir);
  const steps = 28;
  const sweep = (280 * Math.PI) / 180;
  const at = (s: number) => {
    const a = sign * sweep * s;
    return centre.map((c, i) => c + radius * (Math.cos(a) * u[i] + Math.sin(a) * v[i]));
  };
  for (let k = 0; k < steps; k++) {
    const p0 = at(k / steps);
    const p1 = at((k + 1) / steps);
    const along = normalise(p1.map((x, i) => x - p0[i]));
    const [a, b] = frameOf(along);
    for (let j = 0; j < 6; j++) {
      const t0 = (2 * Math.PI * j) / 6;
      const t1 = (2 * Math.PI * (j + 1)) / 6;
      const off = (t: number) => a.map((x, i) => tube * (Math.cos(t) * x + Math.sin(t) * b[i]));
      const o0 = off(t0);
      const o1 = off(t1);
      tri(p0.map((x, i) => x + o0[i]), p1.map((x, i) => x + o0[i]), p1.map((x, i) => x + o1[i]), col, id);
      tri(p0.map((x, i) => x + o0[i]), p1.map((x, i) => x + o1[i]), p0.map((x, i) => x + o1[i]), col, id);
    }
  }
  const end = at(1);
  const before = at(0.95);
  const along = normalise(end.map((x, i) => x - before[i]));
  arrow(end.map((x, i) => x + along[i] * tube * 6), along, tube * 6, tube, col, id, tri);
}

/** A four-sided pyramid under a point: apex at the point, base below it along -Z. */
function pyramid(p: number[], height: number, width: number, col: number[], id: number, tri: Tri) {
  const h = width / 2;
  const z = p[2] - height;
  const corners = [
    [p[0] - h, p[1] - h, z],
    [p[0] + h, p[1] - h, z],
    [p[0] + h, p[1] + h, z],
    [p[0] - h, p[1] + h, z],
  ];
  for (let k = 0; k < 4; k++) tri(p, corners[k], corners[(k + 1) % 4], col, id);
  tri(corners[0], corners[1], corners[2], col, id);
  tri(corners[0], corners[2], corners[3], col, id);
}

// --- small linear algebra, as the CAD view has it -------------------------------------------------

function link(gl: WebGL2RenderingContext, vs: string, fs: string) {
  const program = gl.createProgram()!;
  for (const [type, source] of [
    [gl.VERTEX_SHADER, vs],
    [gl.FRAGMENT_SHADER, fs],
  ] as const) {
    const shader = gl.createShader(type)!;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(`shader: ${gl.getShaderInfoLog(shader)}`);
    gl.attachShader(program, shader);
  }
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(`program: ${gl.getProgramInfoLog(program)}`);
  return program;
}

function buffer(gl: WebGL2RenderingContext, data: Float32Array | Uint32Array) {
  const b = gl.createBuffer()!;
  gl.bindBuffer(gl.ARRAY_BUFFER, b);
  gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
  return b;
}

function attribute(gl: WebGL2RenderingContext, b: WebGLBuffer, location: number, size: number) {
  gl.bindBuffer(gl.ARRAY_BUFFER, b);
  gl.enableVertexAttribArray(location);
  gl.vertexAttribPointer(location, size, gl.FLOAT, false, 0, 0);
}

function cross(a: number[], b: number[]) {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function normalise(v: number[]) {
  const l = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / l, v[1] / l, v[2] / l];
}

function lookAt(eye: number[], target: number[], up: number[]): Float32Array {
  const f = normalise([target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]]);
  const s = normalise(cross(f, up));
  const u = cross(s, f);
  return new Float32Array([
    s[0], u[0], -f[0], 0,
    s[1], u[1], -f[1], 0,
    s[2], u[2], -f[2], 0,
    -(s[0] * eye[0] + s[1] * eye[1] + s[2] * eye[2]),
    -(u[0] * eye[0] + u[1] * eye[1] + u[2] * eye[2]),
    f[0] * eye[0] + f[1] * eye[1] + f[2] * eye[2],
    1,
  ]);
}

function perspective(fovY: number, aspect: number, near: number, far: number): Float32Array {
  const f = 1 / Math.tan(fovY / 2);
  return new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, (2 * far * near) / (near - far), 0]);
}

function multiply(a: Float32Array, b: Float32Array): Float32Array {
  const out = new Float32Array(16);
  for (let column = 0; column < 4; column++) {
    for (let row = 0; row < 4; row++) {
      let sum = 0;
      for (let k = 0; k < 4; k++) sum += a[k * 4 + row] * b[column * 4 + k];
      out[column * 4 + row] = sum;
    }
  }
  return out;
}
