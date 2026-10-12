export default function Frame({ className = "", children, ...rest }) {
  return <div className={`frame ${className}`} {...rest}>{children}</div>;
}
