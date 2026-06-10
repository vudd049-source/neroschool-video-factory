// Cloudflare Worker — бесплатная генерация AI-картинок
// 100 000 запросов/день бесплатно через Workers AI free tier
// Модели: FLUX.1 Schnell (по умолчанию), SDXL Lightning
//
// Установка: см. AGENTS.md

export default {
  async fetch(request, env, ctx) {
    const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type, Authorization' }
    if (request.method === 'OPTIONS') return new Response(null, { headers: cors })
    if (request.method !== 'POST') return new Response(JSON.stringify({ error: 'POST only' }), { status: 405, headers: { ...cors, 'Content-Type': 'application/json' } })
    const auth = request.headers.get('Authorization')
    if (!auth || auth !== 'Bearer ' + (env.API_KEY || '')) return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401, headers: { ...cors, 'Content-Type': 'application/json' } })
    try {
      const body = await request.json()
      if (!body.prompt) return new Response(JSON.stringify({ error: 'Prompt required' }), { status: 400, headers: { ...cors, 'Content-Type': 'application/json' } })
      const model = body.model || '@cf/black-forest-labs/flux-1-schnell'
      const inputs = { prompt: body.prompt }
      const resp = await env.AI.run(model, inputs)
      let b64 = null
      if (typeof resp.image === 'string') b64 = resp.image
      else if (resp instanceof ArrayBuffer) b64 = arrayBufToB64(resp)
      else if (resp.image instanceof ArrayBuffer) b64 = arrayBufToB64(resp.image)
      if (!b64) return new Response(JSON.stringify({ error: 'No image data from: ' + model }), { status: 500, headers: { ...cors, 'Content-Type': 'application/json' } })
      return new Response(JSON.stringify({ image: 'data:image/png;base64,' + b64 }), { headers: { ...cors, 'Content-Type': 'application/json' } })
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { ...cors, 'Content-Type': 'application/json' } })
    }
  }
}
function arrayBufToB64(buf) {
  let b = '', u = new Uint8Array(buf)
  for (let i = 0; i < u.byteLength; i++) b += String.fromCharCode(u[i])
  return btoa(b)
}
