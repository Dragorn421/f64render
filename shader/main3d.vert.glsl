uniform mat4 matMVP;

// Lighting (will compute shade in the end)
uniform vec4 lightColor;
uniform vec3 lightDir;
uniform vec4 ambientColor;

// CC inputs
uniform vec4 colorPrim;
uniform vec4 colorEnv;

// CC config
uniform ivec4 inCC0Color;
uniform ivec4 inCC0Alpha;
uniform ivec4 inCC1Color;
uniform ivec4 inCC1Alpha;
uniform int inFlags;

// VBO data
in vec3 inPos;
in vec3 inNormal;
in vec4 inColor;
in vec2 inUV;

// CC inputs for fragment shader
out vec4 cc_shade;
out flat vec4 cc_shade_flat;
out vec4 cc_env;
out vec4 cc_prim;
out vec2 uv;

// CC settings (enum)
out flat ivec4 cc0Color;
out flat ivec4 cc0Alpha;
out flat ivec4 cc1Color;
out flat ivec4 cc1Alpha;
out flat int flags;

void main() 
{
  // Directional light
  vec3 norm = normalize(inNormal);
  float lightStren = max(dot(norm, lightDir), 0.0);
  vec4 lightTotal = lightColor * lightStren;

  lightTotal += vec4(ambientColor.rgb, 0.0);
  lightTotal = clamp(lightTotal, 0.0, 1.0);  
  
  // Ambient light
  cc_shade.rgb = linearToGamma(lightTotal.rgb);
  cc_shade.a = 1.0;
  cc_shade *= inColor;
  cc_shade_flat = cc_shade;

  cc_env.rgb = linearToGamma(colorEnv.rgb);
  cc_prim.rgb = linearToGamma(colorPrim.rgb);

  uv = inUV;

  flags = inFlags;

  // @TODO: apply tile-settings
  // @TODO: uvgen (f3d + t3d)

  // forward CC (@TODO: do part of this here? e.g. prim/env/shade etc.)
  cc0Color = inCC0Color;
  cc0Alpha = inCC0Alpha;
  cc1Color = inCC1Color;
  cc1Alpha = inCC1Alpha;

  gl_Position = matMVP * vec4(inPos, 1.0);
}