import { handleHome, handleMaterial } from "./handlers/home.js";
import { handleUpload, handleUploadPage } from "./handlers/upload.js";
import { handleDownload } from "./handlers/download.js";
import { handleReport } from "./handlers/report.js";
import { handleAdminAction, handleAdminLogin, handleAdminLogout, handleAdminPage } from "./handlers/admin.js";
import { renderAbout, renderMessage, htmlResponse } from "./pages.js";

export default {
  async fetch(request, env) {
    try {
      return await route(request, env);
    } catch (error) {
      console.error(error && error.stack ? error.stack : error);
      return htmlResponse(renderMessage(
        "服务器出错了",
        `处理这个请求时发生错误：${error.message || error}`,
        [["/", "回到首页"]],
      ), 500);
    }
  },
};

async function route(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method.toUpperCase();

  if (method === "GET" && path === "/") {
    return handleHome(request, env);
  }
  if (method === "GET" && path === "/upload") {
    return handleUploadPage();
  }
  if (method === "POST" && path === "/upload") {
    return handleUpload(request, env);
  }
  if (method === "GET" && path === "/about") {
    return htmlResponse(renderAbout());
  }
  if (method === "GET" && path === "/admin") {
    return handleAdminPage(request, env);
  }
  if (method === "POST" && path === "/admin") {
    return handleAdminLogin(request, env);
  }
  if (method === "GET" && path === "/admin/logout") {
    return handleAdminLogout();
  }
  if (method === "POST" && path === "/admin/action") {
    return handleAdminAction(request, env);
  }
  if (method === "GET" && path.startsWith("/material/")) {
    return handleMaterial(request, env, path.slice("/material/".length));
  }
  if (method === "GET" && path.startsWith("/download/")) {
    return handleDownload(request, env, path.slice("/download/".length));
  }
  if (method === "POST" && path === "/report") {
    return handleReport(request, env);
  }
  if (method === "GET" && path === "/favicon.ico") {
    return new Response(null, { status: 204, headers: { "Content-Length": "0" } });
  }

  return htmlResponse(renderMessage(
    "页面不存在",
    `没有找到 ${path} 这个地址。`,
    [["/", "回到首页"]],
  ), 404);
}
