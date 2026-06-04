export default async (req) => {
  const url = new URL(req.url);
  const query = url.searchParams.get('q') || '';

  const indexUrl = new URL('/packages/index.json', url.origin);
  const res = await fetch(indexUrl);
  const data = await res.json();

  const q = query.toLowerCase();
  const results = data.packages.filter(p => {
    const name = (p.name || '').toLowerCase();
    const desc = (p.description || '').toLowerCase();
    const author = (p.author || '').toLowerCase();
    const keywords = (p.keywords || []).map(k => k.toLowerCase());
    return name.includes(q) || desc.includes(q) || author.includes(q) ||
           keywords.some(kw => kw.includes(q));
  });

  return new Response(JSON.stringify({ count: results.length, packages: results }), {
    headers: { 'Content-Type': 'application/json' },
  });
};

export const config = { runtime: 'edge' };
