/**
 * WebGL2 renderer for a face-tagged CAD tessellation.
 *
 * Three ideas carry the whole thing.
 *
 * **Face state lives in a texture, not in the geometry.** Selecting a face must not re-upload 13 MB
 * of vertices. Instead every face id indexes a small RGBA8 texture holding its state, and the
 * fragment shader reads its own face's texel. Changing a selection writes a few bytes.
 *
 * **Picking is a second render pass.** WebGL2 has no primitive id, so the face id travels as a
 * vertex attribute and is written as colour into an offscreen buffer. Reading one pixel under the
 * cursor gives an exact hit with no ray casting and no tolerance to tune.
 *
 * **Normals arrive per face.** The server averages them within a CAD face rather than across
 * vertices, so a bore shades smoothly while the chamfer beside it keeps its edge. Nothing here
 * needs to guess at a crease angle.
 */

import type { Mesh } from "../api/client";

export type ColourMode = "surface" | "frozen" | "exterior";

export interface FaceState {
  selected: Set<number>;
  hovered: number | null;
  frozen: Set<number>;
  /** Faces reachable from outside the casting, for the exterior colour mode. */
  exterior: Set<number>;
}

const VERTEX_SHADER = `#version 300 es
precision highp float;

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in uint a_faceId;

uniform mat4 u_viewProjection;
uniform mat4 u_model;

out vec3 v_normal;
out vec3 v_worldPosition;
flat out uint v_faceId;

void main() {
  vec4 world = u_model * vec4(a_position, 1.0);
  v_worldPosition = world.xyz;
  v_normal = mat3(u_model) * a_normal;
  v_faceId = a_faceId;
  gl_Position = u_viewProjection * world;
}`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;
precision highp usampler2D;

in vec3 v_normal;
in vec3 v_worldPosition;
flat in uint v_faceId;

uniform sampler2D u_faceState;
uniform int u_faceStateWidth;
uniform vec3 u_eye;
uniform int u_colourMode;

out vec4 fragColour;

// Engineering-sheet palette, matching ui/src/styles/tokens.css. Kept in sync by hand because a
// shader cannot read CSS custom properties, and the set is small enough that drift is visible.
const vec3 INK        = vec3(0.106, 0.122, 0.118);
const vec3 STEEL      = vec3(0.647, 0.671, 0.663);
const vec3 BLUE       = vec3(0.059, 0.239, 0.569);
const vec3 MEASURED   = vec3(0.184, 0.420, 0.310);
const vec3 OCHRE      = vec3(0.541, 0.416, 0.122);
const vec3 INTERIOR   = vec3(0.478, 0.502, 0.494);

vec4 faceState(uint faceId) {
  int index = int(faceId);
  int width = u_faceStateWidth;
  ivec2 texel = ivec2(index % width, index / width);
  return texelFetch(u_faceState, texel, 0);
}

void main() {
  vec3 normal = normalize(v_normal);
  vec3 viewDirection = normalize(u_eye - v_worldPosition);

  // Two-sided: a bore's far wall is seen from behind, and lighting it as if it faced away turns
  // every bore into a black hole.
  if (dot(normal, viewDirection) < 0.0) normal = -normal;

  vec4 state = faceState(v_faceId);
  bool isSelected = state.r > 0.5;
  bool isFrozen   = state.g > 0.5;
  bool isHovered  = state.b > 0.5;
  bool isExterior = state.a > 0.5;

  vec3 base = STEEL;
  if (u_colourMode == 1) {
    // Frozen mode answers one question only - what can never move - so everything else stays
    // neutral rather than competing for attention.
    base = isFrozen ? MEASURED : STEEL;
  } else if (u_colourMode == 2) {
    base = isExterior ? OCHRE : INTERIOR;
  }
  // Nothing tints the default view. An always-on colour reads as a selection the user did not
  // make, and it competes with the one they did. Controlled faces get their own mode, entered
  // deliberately; everywhere else the fact is text in the panel.
  if (isSelected) base = mix(base, BLUE, 0.72);
  if (isHovered) base = mix(base, vec3(1.0), 0.28);

  // A key light plus a dim fill from below. Enough to read form on a grey casting without
  // pretending to be a rendering of anything.
  vec3 keyDirection = normalize(vec3(0.45, 0.35, 0.82));
  float key = max(dot(normal, keyDirection), 0.0);
  float fill = max(dot(normal, vec3(0.0, 0.0, -1.0)), 0.0) * 0.22;
  float rim = pow(1.0 - max(dot(normal, viewDirection), 0.0), 2.5) * 0.28;

  vec3 colour = base * (0.34 + 0.66 * key + fill) + rim * mix(base, vec3(1.0), 0.5);
  colour = mix(colour, INK, 0.04);
  fragColour = vec4(pow(colour, vec3(0.4545)), 1.0);
}`;

const PICK_VERTEX_SHADER = `#version 300 es
precision highp float;
layout(location = 0) in vec3 a_position;
layout(location = 2) in uint a_faceId;
uniform mat4 u_viewProjection;
uniform mat4 u_model;
flat out uint v_faceId;
void main() {
  v_faceId = a_faceId;
  gl_Position = u_viewProjection * u_model * vec4(a_position, 1.0);
}`;

const PICK_FRAGMENT_SHADER = `#version 300 es
precision highp float;
flat in uint v_faceId;
out vec4 fragColour;
void main() {
  // Face id + 1, little-endian across RGB, so 0 can mean "nothing here". Three bytes covers
  // 16.7 million faces against this part's 2167.
  uint id = v_faceId + 1u;
  fragColour = vec4(
    float(id & 255u) / 255.0,
    float((id >> 8u) & 255u) / 255.0,
    float((id >> 16u) & 255u) / 255.0,
    1.0
  );
}`;

export class Renderer {
  private gl: WebGL2RenderingContext;
  private program: WebGLProgram;
  private pickProgram: WebGLProgram;
  private vao: WebGLVertexArrayObject;
  private pickVao: WebGLVertexArrayObject;
  private faceStateTexture: WebGLTexture;
  private faceStateData: Uint8Array;
  private faceStateWidth: number;
  private pickFramebuffer: WebGLFramebuffer;
  private pickTexture: WebGLTexture;
  private pickDepth: WebGLRenderbuffer;
  private pickSize = { width: 0, height: 0 };
  private vertexCount: number;
  private faceCount: number;

  colourMode: ColourMode = "surface";

  /** The model extent the camera was framed to. Zoom limits derive from it. */
  private extent = 1000;

  /** Orbit camera state, in the part's own millimetre frame. */
  camera = {
    target: [0, 0, 0] as [number, number, number],
    distance: 3000,
    azimuth: 0.9,
    elevation: 0.55,
    fovY: 0.7,
    near: 1,
    far: 20000,
  };

  constructor(
    private canvas: HTMLCanvasElement,
    mesh: Mesh,
    faceCount: number,
  ) {
    const gl = canvas.getContext("webgl2", { antialias: true, depth: true });
    if (!gl) throw new Error("WebGL2 is not available in this browser");
    this.gl = gl;
    this.vertexCount = mesh.vertexCount;
    this.faceCount = faceCount;

    this.program = linkProgram(gl, VERTEX_SHADER, FRAGMENT_SHADER);
    this.pickProgram = linkProgram(gl, PICK_VERTEX_SHADER, PICK_FRAGMENT_SHADER);

    const positionBuffer = createBuffer(gl, mesh.positions);
    const normalBuffer = createBuffer(gl, mesh.normals);
    const faceIdBuffer = createBuffer(gl, mesh.faceIds);

    this.vao = gl.createVertexArray()!;
    gl.bindVertexArray(this.vao);
    bindFloatAttribute(gl, positionBuffer, 0, 3);
    bindFloatAttribute(gl, normalBuffer, 1, 3);
    bindIntAttribute(gl, faceIdBuffer, 2);
    gl.bindVertexArray(null);

    this.pickVao = gl.createVertexArray()!;
    gl.bindVertexArray(this.pickVao);
    bindFloatAttribute(gl, positionBuffer, 0, 3);
    bindIntAttribute(gl, faceIdBuffer, 2);
    gl.bindVertexArray(null);

    // One texel per face, wrapped at 512 so the texture stays square-ish for any part size.
    this.faceStateWidth = 512;
    const rows = Math.ceil(faceCount / this.faceStateWidth);
    this.faceStateData = new Uint8Array(this.faceStateWidth * rows * 4);
    this.faceStateTexture = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, this.faceStateTexture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(
      gl.TEXTURE_2D, 0, gl.RGBA8, this.faceStateWidth, rows, 0,
      gl.RGBA, gl.UNSIGNED_BYTE, this.faceStateData,
    );

    this.pickFramebuffer = gl.createFramebuffer()!;
    this.pickTexture = gl.createTexture()!;
    this.pickDepth = gl.createRenderbuffer()!;

    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.CULL_FACE);
    // Both faces drawn: a bore's far wall is genuinely visible through its own opening, and
    // culling it leaves a hole in the picture where there is metal.
    gl.disable(gl.CULL_FACE);
  }

  /** Frame the part, from its bounding box. */
  frame(bbox: number[]): void {
    const [x0, y0, z0, x1, y1, z1] = bbox;
    this.camera.target = [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2];
    const extent = Math.max(x1 - x0, y1 - y0, z1 - z0);
    this.extent = extent;
    this.camera.distance = extent * 1.7;
    this.camera.far = extent * 12;
    this.camera.near = extent / 500;
  }

  setFaceState(state: FaceState): void {
    this.faceStateData.fill(0);
    for (const id of state.frozen) this.faceStateData[id * 4 + 1] = 255;
    for (const id of state.exterior) this.faceStateData[id * 4 + 3] = 255;
    for (const id of state.selected) this.faceStateData[id * 4 + 0] = 255;
    if (state.hovered !== null && state.hovered >= 0) {
      this.faceStateData[state.hovered * 4 + 2] = 255;
    }

    const gl = this.gl;
    const rows = Math.ceil(this.faceCount / this.faceStateWidth);
    gl.bindTexture(gl.TEXTURE_2D, this.faceStateTexture);
    gl.texSubImage2D(
      gl.TEXTURE_2D, 0, 0, 0, this.faceStateWidth, rows,
      gl.RGBA, gl.UNSIGNED_BYTE, this.faceStateData,
    );
  }

  render(): void {
    const gl = this.gl;
    const { width, height } = this.resizeToDisplay();
    if (width === 0 || height === 0) return;

    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, width, height);
    gl.clearColor(0.949, 0.953, 0.945, 1.0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    const viewProjection = this.viewProjection(width / height);
    const eye = this.eyePosition();

    gl.useProgram(this.program);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.program, "u_viewProjection"), false, viewProjection);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.program, "u_model"), false, IDENTITY);
    gl.uniform3fv(gl.getUniformLocation(this.program, "u_eye"), eye);
    gl.uniform1i(
      gl.getUniformLocation(this.program, "u_colourMode"),
      this.colourMode === "surface" ? 0 : this.colourMode === "frozen" ? 1 : 2,
    );
    gl.uniform1i(gl.getUniformLocation(this.program, "u_faceStateWidth"), this.faceStateWidth);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.faceStateTexture);
    gl.uniform1i(gl.getUniformLocation(this.program, "u_faceState"), 0);

    gl.bindVertexArray(this.vao);
    gl.drawArrays(gl.TRIANGLES, 0, this.vertexCount);
    gl.bindVertexArray(null);
  }

  /**
   * Which CAD face is under this pixel, or null.
   *
   * Renders ids into an offscreen buffer and reads one pixel. Exact by construction: no ray, no
   * tolerance, and a hit on a one-pixel sliver is as reliable as a hit on a whole panel.
   */
  pick(pixelX: number, pixelY: number): number | null {
    const gl = this.gl;
    const { width, height } = this.pickSizeForCanvas();
    this.ensurePickTarget(width, height);

    gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickFramebuffer);
    gl.viewport(0, 0, width, height);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    gl.useProgram(this.pickProgram);
    gl.uniformMatrix4fv(
      gl.getUniformLocation(this.pickProgram, "u_viewProjection"), false,
      this.viewProjection(width / height),
    );
    gl.uniformMatrix4fv(gl.getUniformLocation(this.pickProgram, "u_model"), false, IDENTITY);
    gl.bindVertexArray(this.pickVao);
    gl.drawArrays(gl.TRIANGLES, 0, this.vertexCount);
    gl.bindVertexArray(null);

    const pixel = new Uint8Array(4);
    const x = Math.round(pixelX);
    const y = Math.round(height - pixelY);
    if (x < 0 || y < 0 || x >= width || y >= height) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      return null;
    }
    gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);

    const id = pixel[0] | (pixel[1] << 8) | (pixel[2] << 16);
    return id === 0 ? null : id - 1;
  }

  /**
   * Turntable orbit, following "grab the part and drag it".
   *
   * Both signs are negative because both axes obey the same rule: the surface under the cursor
   * follows the cursor. Drag right and the near face travels right, which means the camera has to
   * swing the other way, so azimuth decreases. Drag up and the near face travels up, which means
   * the camera drops, so elevation decreases too - and screen Y already grows downward, so a
   * drag upward is a negative delta and the minus sign restores it.
   *
   * The elevation term was positive at first, which made vertical the odd one out: horizontal
   * orbit and both pan axes dragged the part, while vertical pushed it away. That reads as
   * broken rather than merely unfamiliar, because two of the three axes set the expectation.
   */
  orbit(deltaX: number, deltaY: number): void {
    this.camera.azimuth -= deltaX * 0.008;
    this.camera.elevation = clamp(this.camera.elevation + deltaY * 0.008, -1.5, 1.5);
  }

  pan(deltaX: number, deltaY: number): void {
    const scale = this.camera.distance * 0.0013;
    const [right, up] = this.basis();
    for (let i = 0; i < 3; i++) {
      this.camera.target[i] += (-right[i] * deltaX + up[i] * deltaY) * scale;
    }
  }

  zoom(delta: number): void {
    this.camera.distance = clamp(
      this.camera.distance * Math.exp(delta * 0.0012),
      this.extent * 0.02,
      this.extent * 20,
    );
  }

  private pickSizeForCanvas() {
    // Half resolution. A pick is a single pixel read and half the pixels is a quarter of the
    // fill, which is the difference between a hover feeling instant and feeling sticky.
    return {
      width: Math.max(1, Math.floor(this.canvas.width / 2)),
      height: Math.max(1, Math.floor(this.canvas.height / 2)),
    };
  }

  private ensurePickTarget(width: number, height: number): void {
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

  private resizeToDisplay() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.floor(this.canvas.clientWidth * ratio);
    const height = Math.floor(this.canvas.clientHeight * ratio);
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    return { width, height };
  }

  private eyePosition(): Float32Array {
    const { target, distance, azimuth, elevation } = this.camera;
    const cosE = Math.cos(elevation);
    return new Float32Array([
      target[0] + distance * cosE * Math.cos(azimuth),
      target[1] + distance * cosE * Math.sin(azimuth),
      target[2] + distance * Math.sin(elevation),
    ]);
  }

  private basis(): [number[], number[]] {
    const { azimuth, elevation } = this.camera;
    const forward = [
      -Math.cos(elevation) * Math.cos(azimuth),
      -Math.cos(elevation) * Math.sin(azimuth),
      -Math.sin(elevation),
    ];
    // Z is up: the part is shown in its own CAD frame, not in a graphics convention.
    const right = normalise(cross(forward, [0, 0, 1]));
    const up = normalise(cross(right, forward));
    return [right, up];
  }

  private viewProjection(aspect: number): Float32Array {
    const eye = this.eyePosition();
    const { target, fovY, near, far } = this.camera;
    const view = lookAt([eye[0], eye[1], eye[2]], target, [0, 0, 1]);
    const projection = perspective(fovY, aspect, near, far);
    return multiply(projection, view);
  }
}

const IDENTITY = new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);

function linkProgram(gl: WebGL2RenderingContext, vertexSource: string, fragmentSource: string) {
  const program = gl.createProgram()!;
  for (const [type, source] of [
    [gl.VERTEX_SHADER, vertexSource],
    [gl.FRAGMENT_SHADER, fragmentSource],
  ] as const) {
    const shader = gl.createShader(type)!;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      throw new Error(`shader compile failed: ${gl.getShaderInfoLog(shader)}`);
    }
    gl.attachShader(program, shader);
  }
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(`program link failed: ${gl.getProgramInfoLog(program)}`);
  }
  return program;
}

function createBuffer(gl: WebGL2RenderingContext, data: Float32Array | Uint32Array) {
  const buffer = gl.createBuffer()!;
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
  return buffer;
}

function bindFloatAttribute(
  gl: WebGL2RenderingContext, buffer: WebGLBuffer, location: number, size: number,
) {
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.enableVertexAttribArray(location);
  gl.vertexAttribPointer(location, size, gl.FLOAT, false, 0, 0);
}

function bindIntAttribute(gl: WebGL2RenderingContext, buffer: WebGLBuffer, location: number) {
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.enableVertexAttribArray(location);
  gl.vertexAttribIPointer(location, 1, gl.UNSIGNED_INT, 0, 0);
}

function clamp(value: number, low: number, high: number) {
  return Math.min(Math.max(value, low), high);
}

function cross(a: number[], b: number[]) {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function normalise(v: number[]) {
  const length = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / length, v[1] / length, v[2] / length];
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
  return new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) / (near - far), -1,
    0, 0, (2 * far * near) / (near - far), 0,
  ]);
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
