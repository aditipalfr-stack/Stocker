if (typeof globalThis.CustomEvent === 'undefined') {
  class CustomEvent extends Event {
    constructor(type, options) {
      super(type, options);
      this.detail = options ? options.detail : null;
    }
  }
  globalThis.CustomEvent = CustomEvent;
}
