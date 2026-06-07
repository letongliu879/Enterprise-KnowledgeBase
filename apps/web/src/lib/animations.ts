import { Variants, Transition } from "framer-motion";

export const easeOut: Transition = {
  duration: 0.35,
  ease: [0.25, 0.1, 0.25, 1],
};

export const easeInOut: Transition = {
  duration: 0.3,
  ease: [0.4, 0, 0.2, 1],
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: easeOut,
  },
};

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: easeOut,
  },
};

export const fadeInDown: Variants = {
  hidden: { opacity: 0, y: -12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: easeOut,
  },
};

export const fadeInLeft: Variants = {
  hidden: { opacity: 0, x: -12 },
  visible: {
    opacity: 1,
    x: 0,
    transition: easeOut,
  },
};

export const fadeInRight: Variants = {
  hidden: { opacity: 0, x: 12 },
  visible: {
    opacity: 1,
    x: 0,
    transition: easeOut,
  },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: easeOut,
  },
};

export const slideInFromLeft: Variants = {
  hidden: { x: -240, opacity: 0 },
  visible: {
    x: 0,
    opacity: 1,
    transition: {
      duration: 0.3,
      ease: [0.25, 0.1, 0.25, 1],
    },
  },
  exit: {
    x: -240,
    opacity: 0,
    transition: {
      duration: 0.2,
      ease: "easeIn",
    },
  },
};

export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1,
    },
  },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: [0.25, 0.1, 0.25, 1],
    },
  },
};

export const cardHover = {
  rest: {
    y: 0,
    boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
    borderColor: "rgba(255,255,255,0.06)",
  },
  hover: {
    y: -2,
    boxShadow: "0 10px 40px rgba(0,0,0,0.4), 0 0 20px rgba(99,102,241,0.1)",
    borderColor: "rgba(99,102,241,0.3)",
    transition: {
      duration: 0.25,
      ease: "easeOut",
    },
  },
};

export const buttonTap = {
  scale: 0.97,
  transition: { duration: 0.1 },
};

export const pageTransition: Variants = {
  initial: { opacity: 0, y: 4 },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.25,
      ease: [0.25, 0.1, 0.25, 1],
    },
  },
};

export const overlayFade: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.2 },
  },
  exit: {
    opacity: 0,
    transition: { duration: 0.15 },
  },
};

export const dropdownMenu: Variants = {
  hidden: {
    opacity: 0,
    y: -4,
    scale: 0.97,
  },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.2,
      ease: [0.25, 0.1, 0.25, 1],
    },
  },
  exit: {
    opacity: 0,
    y: -4,
    scale: 0.97,
    transition: { duration: 0.15 },
  },
};
