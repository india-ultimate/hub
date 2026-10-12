const base = require("../../frontend/webpack.config.js");

// Not webpack-cli's `extends`: that would append this proxy to the base
// one, whose port-8000 entry matches first.
module.exports = {
  ...base,
  devServer: {
    ...base.devServer,
    port: 9982,
    // 127.0.0.1, not localhost: since Node 17, localhost can resolve to ::1
    // first, where runserver isn't listening (CI was held on Node 16 for it).
    proxy: [
      {
        context: ["/api", "/admin", "/static", "/uploads", "/ckeditor"],
        target: "http://127.0.0.1:9981"
      }
    ]
  }
};
