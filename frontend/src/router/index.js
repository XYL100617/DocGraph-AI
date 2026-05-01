import { createRouter, createWebHistory } from "vue-router"

import Main from "../views/Main.vue"
import History from "../views/History.vue"
import GraphView from "../views/GraphView.vue"
import Report from "../views/Report.vue"
import About from "../views/About.vue"

const routes = [
  {
    path: "/",
    redirect: "/main"
  },
  {
    path: "/main",
    component: Main
  },
  {
    path: "/history",
    component: History
  },
  {
    path: "/graph",
    component: GraphView
  },
  {
    path: "/report",
    component: Report
  },
  {
    path: "/about",
    component: About
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router