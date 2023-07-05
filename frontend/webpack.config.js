const path = require("path");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

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
        test: /\.css$/,
        use: [MiniCssExtractPlugin.loader, "css-loader", "postcss-loader"]
      },
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader",
          options: {
            presets: ["@babel/preset-env", "solid"]
          }
        }
      },
      {
        test: /\.js$/,
        include: path.resolve(__dirname, "src/components"),
        use: [
          "solid-hot-loader",
          {
            loader: "babel-loader",
            options: {
              presets: ["@babel/preset-env", "solid"]
            }
          }
        ]
      }
    ]
  },
  plugins: [
    // MiniCssExtractPlugin to extract css into separate files
    new MiniCssExtractPlugin({
      filename: "main.css"
    })
  ],
  devServer: {
    static: {
      directory: path.resolve(__dirname),
      staticOptions: {
        index: "index.html"
      }
    },
    hot: true,
    port: 3000,
    historyApiFallback: true,
    proxy: {
      "/api": "http://localhost:8000"
    }
  }
};
