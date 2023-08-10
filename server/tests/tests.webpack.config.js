const path = require("path");
module.exports = {
  extends: "webpack.config.js",
  devServer: {
    port: 9982,
    proxy: {
      "/api": "http://localhost:9981",
      "/admin": "http://localhost:9981",
      "/static": "http://localhost:9981",
      "/uploads": "http://localhost:9981",
    },
  },
};
