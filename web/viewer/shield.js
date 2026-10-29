// Fractal shielding on the Brow's ram faces (build.json shield, from the runtime manifest's look.exterior.grammar.fractal_shield): the
// hexagonal facing plates with Sierpinski-subdivided triangles, drawn by the same GLSL the Godot runtime includes
// (godot/shaders/fractal_shield.gdshaderinc, copied into the site as shield_file). The imported materials are patched in place, so every
// mesh keeps its own material object (the appearance resolver and Reset compare by identity) and its colour, roughness and alpha; the
// pattern only scales the colour and bends the normal on forward-facing faces. Each level fades in by its on-screen size (distance LOD).
// Presentation only: no geometry, pick or spacecraft fact changes.

const NAME = /^Runtime_WF_MAT_(.+)_\d+$/;

export function patchShield(model, block, glsl) {
  if (!block || block.pattern !== 'fractal_hex' || !glsl) return 0;
  const names = new Set(block.materials);
  const done = new Set();
  model.traverse(o => {
    if (!o.isMesh) return;
    for (const m of [].concat(o.material)) {
      const hit = NAME.exec(m.name || '');
      if (!hit || !names.has(hit[1]) || done.has(m) || !m.isMeshStandardMaterial) continue;
      done.add(m);
      m.userData.fractalShield = true;
      m.customProgramCacheKey = () => 'wf-fractal-shield';
      m.onBeforeCompile = shader => {
        for (const [k, v] of Object.entries(block.uniforms)) shader.uniforms[k] = { value: v };
        shader.uniforms.fs_x_min = { value: block.x_min_m };
        shader.uniforms.fs_nx_min = { value: block.normal_x_min };
        shader.vertexShader = 'varying vec3 vFsWorld;\nvarying vec3 vFsNormal;\n' + shader.vertexShader.replace('#include <fog_vertex>',
          '#include <fog_vertex>\n  vFsWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;\n  vFsNormal = normalize(mat3(modelMatrix) * objectNormal);');
        shader.fragmentShader = 'varying vec3 vFsWorld;\nvarying vec3 vFsNormal;\nuniform float fs_x_min;\nuniform float fs_nx_min;\n' + glsl + '\n'
          + shader.fragmentShader
            .replace('#include <color_fragment>', `#include <color_fragment>
  // runtime axes (x, z, -y) back to Blender (y, z) in the plane across the ship axis
  vec2 fsP = vec2(-vFsWorld.z, vFsWorld.y);
  vec2 fsW = fwidth(fsP);
  float fsV;
  float fsH;
  fs_pattern(fsP, max(max(fsW.x, fsW.y), 1e-5), fsV, fsH);
  float fsOn = (normalize(vFsNormal).x > fs_nx_min && vFsWorld.x > fs_x_min) ? 1.0 : 0.0;
  diffuseColor.rgb *= mix(1.0, fsV, fsOn);`)
            .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
  normal = fs_bump(dFdx(-vViewPosition), dFdy(-vViewPosition), normal, dFdx(fsH * fsOn), dFdy(fsH * fsOn));`);
      };
      m.needsUpdate = true;
    }
  });
  return done.size;
}
