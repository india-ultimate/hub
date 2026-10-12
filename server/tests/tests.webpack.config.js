const path = require("path");
module.exports = {
  extends: "webpack.config.js",
  devServer: {
    port: 9982,
    // 127.0.0.1, not localhost: since Node 17, localhost can resolve to ::1
    // first, where runserver isn't listening (CI was held on Node 16 for it).
    proxy: {
      "/api": "http://127.0.0.1:9981",
      "/admin": "http://127.0.0.1:9981",
      "/static": "http://127.0.0.1:9981",
      "/uploads": "http://127.0.0.1:9981"
    }
  }
};
