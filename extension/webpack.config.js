const path = require('path');

module.exports = [
  // 主扩展入口
  {
    target: 'node',
    mode: 'production',
    entry: './src/extension.ts',
    output: {
      path: path.resolve(__dirname, 'out'),
      filename: 'extension.js',
      libraryTarget: 'commonjs2',
    },
    externals: {
      vscode: 'commonjs vscode',
    },
    resolve: {
      extensions: ['.ts', '.js'],
    },
    module: {
      rules: [
        {
          test: /\.ts$/,
          use: 'ts-loader',
          exclude: /node_modules/,
        },
      ],
    },
  },
  // Webview 入口
  {
    target: 'web',
    mode: 'production',
    performance: {
      hints: false, // webview 是本地按需加载，大小不影响性能
    },
    entry: {
      simSettings: './src/webview/simSettings/index.tsx',
      prefillParams: './src/webview/prefillParams/index.tsx',
      replay: './src/webview/replay/index.tsx',
      configPage: './src/webview/configPage/index.tsx',
      initConfig: './src/webview/initConfig/index.tsx',
    },
    output: {
      path: path.resolve(__dirname, 'out', 'webview'),
      filename: '[name].js',
    },
    resolve: {
      extensions: ['.ts', '.tsx', '.js', '.jsx'],
    },
    module: {
      rules: [
        {
          test: /\.tsx?$/,
          use: {
            loader: 'ts-loader',
            options: {
              configFile: path.resolve(__dirname, 'src/webview/tsconfig.json'),
            },
          },
          exclude: /node_modules/,
        },
        {
          test: /\.css$/,
          use: ['style-loader', 'css-loader'],
        },
        {
          test: /\.less$/,
          use: [
            'style-loader',
            'css-loader',
            {
              loader: 'less-loader',
              options: {
                lessOptions: {
                  javascriptEnabled: true,
                },
              },
            },
          ],
        },
        {
          test: /\.(png|jpg|gif|svg)$/i,
          type: 'asset/inline',
        },
      ],
    },
  },
];
