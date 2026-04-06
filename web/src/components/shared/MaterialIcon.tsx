interface MaterialIconProps {
  name: string;
  size?: number;
  className?: string;
}

export function MaterialIcon({ name, size, className }: MaterialIconProps) {
  const classes = ["material-symbols-outlined", className].filter(Boolean).join(" ");
  return (
    <span className={classes} style={size ? { fontSize: `${size}px` } : undefined}>
      {name}
    </span>
  );
}
