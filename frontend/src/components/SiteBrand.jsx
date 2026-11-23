import { NavLink } from "react-router-dom";
import udmlogo from "../assets/udmlogo.png";

export default function SiteBrand({ to = "/", className = "brand", title, subtitle, dark = false }) {
  return (
    <NavLink to={to} className={`${className} ${dark ? "brand-dark" : ""}`}>
      <img src={udmlogo} alt="Universidad de Manila" className="udm-logo-nav" />
      {(title || subtitle) && (
        <span>
          {title ? <strong>{title}</strong> : null}
          {subtitle ? <small>{subtitle}</small> : null}
        </span>
      )}
    </NavLink>
  );
}
