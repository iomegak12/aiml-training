import Icon from './Icon'
import styles from './Button.module.css'

/** variant: "primary" (purple), "gradient" (brand pill), "outline" (soft purple) or "ghost". */
export default function Button({ variant = 'primary', size = 'md', icon, iconRight, children, className = '', as: As = 'button', ...props }) {
  const classes = [styles.button, styles[variant], styles[size], className].join(' ')
  return (
    <As className={classes} {...(As === 'button' && !props.type ? { type: 'button' } : {})} {...props}>
      {icon && <Icon name={icon} size={size === 'sm' ? 16 : 18} />}
      {children && <span>{children}</span>}
      {iconRight && <Icon name={iconRight} size={size === 'sm' ? 16 : 18} />}
    </As>
  )
}
