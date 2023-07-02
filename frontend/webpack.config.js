const path = require("path");

module.exports = {
  entry: "./src/index.js",
  output: {
    path: path.resolve(__dirname, "dist"),
    filename: "bundle.js"
  },
  resolve: {
    extensions: [".js"]
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader",
          options: {
            presets: ["@babel/preset-env", "solid"]
          }
        }
      }
    ]
  },
  devServer: {
    static: {
      directory: path.resolve(__dirname),
      staticOptions: {
        index: "index.html"
      }
    },
    hot: true,
    port: 3000,
    historyApiFallback: true
  }
};
