
<h1 align="center">
  <br>
  K-ICS Web UI
</h1>

_<p align="center">K-ICS Chat UI for AI-assisted data work.</p>_

<p align="center">
  <a href="https://github.com/hua7448/db-gpt-chat/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg?label=License&style=flat" />
  </a>
  <a href="https://github.com/hua7448/db-gpt-chat/releases">
    <img alt="Release Notes" src="https://img.shields.io/github/release/hua7448/db-gpt-chat" />
  </a>
  <a href="https://github.com/hua7448/db-gpt-chat/issues">
    <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/hua7448/db-gpt-chat" />
  </a>
  <a href="https://discord.gg/7uQnPuveTY">
    <img alt="Discord" src="https://dcbadge.vercel.app/api/server/7uQnPuveTY?compact=true&style=flat" />
  </a>
</p>

---

## 👋 Introduction

***K-ICS Web UI*** is the downstream-branded chat interface for the
[K-ICS](https://github.com/hua7448/db-gpt-chat) runtime. It is an **open source
chat UI** for AI-assisted data work.

K-ICS Web UI is a Tailwind and Next.js based chat UI for AI and GPT projects. It
adds polished markdown rendering and custom views for plugin execution,
knowledge references, charts, and related AI workflows.

## 💪🏻 Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) >= 16
- [npm](https://npmjs.com/) >= 8
- [yarn](https://yarnpkg.com/) >= 1.22
- Supported OSes: Linux, macOS and Windows

### Installation

Using **Yarn** is recommended for dependency management.

```sh
# Install dependencies
npm install
yarn install
```

### Usage
```sh
cp .env.template .env
```
edit the `API_BASE_URL` to the real address

```sh
# development model
npm run dev
yarn dev
```

## 🚀 Use In K-ICS

```sh
bash ../scripts/build_web_static.sh
```

## 📚 Documentation

For full documentation, see the [K-ICS documentation](../docs/).


## Usage
  [gpt-vis](https://github.com/eosphoros-ai/GPT-Vis) for markdown support.
  [ant-design](https://github.com/ant-design/ant-design) for ui components.
  [next.js](https://github.com/vercel/next.js) for server side rendering.
  [@antv/g2](https://github.com/antvis/g2#readme) for charts.

## License

K-ICS Web UI is licensed under the [MIT License](LICENSE).

---

Use K-ICS Web UI to build tailored interfaces for your AI and GPT projects.

🌟 If you find it helpful, don't forget to give it a star on GitHub! Stars are like little virtual hugs that keep us going! We appreciate every single one we receive.

For any queries or issues, feel free to open an [issue](https://github.com/hua7448/db-gpt-chat/issues) on the repository.

Happy coding! 😊


## K-ICS Web UI installation

### deploy in local environment:
