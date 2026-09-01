import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { transform } from 'sucrase';

if (typeof globalThis.CustomEvent === 'undefined') {
  class CustomEvent extends Event {
    constructor(type, options) {
      super(type, options);
      this.detail = options?.detail;
    }
  }
  globalThis.CustomEvent = CustomEvent;
}

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'node:util' || specifier === 'util') {
    return {
      url: 'file:///home/dev/Projects/stocker/frontend/tests/virtual-util.mjs',
      shortCircuit: true
    };
  }
  return nextResolve(specifier, context);
}

export async function load(url, context, nextLoad) {
  if (url === 'file:///home/dev/Projects/stocker/frontend/tests/virtual-util.mjs') {
    return {
      format: 'module',
      shortCircuit: true,
      source: `
        import { createRequire } from 'node:module';
        const require = createRequire(import.meta.url);
        const allUtil = require('node:util');
        export const format = allUtil.format;
        export const formatWithOptions = allUtil.formatWithOptions || allUtil.format;
        export const inspect = allUtil.inspect;
        export const parseEnv = allUtil.parseEnv || ((s) => ({}));
        export const promisify = allUtil.promisify;
        export const stripVTControlCharacters = allUtil.stripVTControlCharacters || ((s) => s);
        export const styleText = allUtil.styleText || ((_f, text) => text);
        export const deprecate = allUtil.deprecate;
        export const callbackify = allUtil.callbackify;
        export const types = allUtil.types;
        export const isDeepStrictEqual = allUtil.isDeepStrictEqual;
        export const TextDecoder = allUtil.TextDecoder;
        export const TextEncoder = allUtil.TextEncoder;
        export const inherits = allUtil.inherits;
        export const debuglog = allUtil.debuglog;
        export default allUtil;
      `
    };
  }
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
