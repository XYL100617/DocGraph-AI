import { createApp } from "vue"
import App from "./App.vue"
import router from "./router"
import "./style.css"

localStorage.removeItem("themeMode")
document.documentElement.removeAttribute("data-theme")
document.body.removeAttribute("data-theme")

createApp(App)
  .use(router)
  .mount("#app")