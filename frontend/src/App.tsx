import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "@/components/layout/Layout.tsx";
import Home from "./pages/Home";
import LoginPage from "./pages/LoginPage.tsx";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
