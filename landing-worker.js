const DESIGN_VERSION = "20261009-design2";

export default {
  fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/" || url.pathname === "/index.html" || url.pathname === "/styles.css") {
      url.searchParams.set("v", DESIGN_VERSION);
    }

    return env.ASSETS.fetch(new Request(url, request));
  },
};
