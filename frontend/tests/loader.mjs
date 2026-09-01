import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { transform } from 'sucrase';

export async function load(url, context, nextLoad) {
  if (url.endsWith('.ts') || url.endsWith('.tsx')) {
    const raw = await readFile(fileURLToPath(url), 'utf8');
    const { code } = transform(raw, { transforms: ['typescript', 'jsx'] });
    return {
      format: 'module',
      shortCircuit: true,
      source: code
    };
  }
  return nextLoad(url, context);
}
