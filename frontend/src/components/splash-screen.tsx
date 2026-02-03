"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

export function SplashScreen({ onComplete }: { onComplete: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onComplete, 2500);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden"
        initial={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Animated background gradient */}
        <motion.div
          className="absolute inset-0 bg-zinc-950"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
        />

        {/* Radial glow pulses */}
        <motion.div
          className="absolute w-[600px] h-[600px] rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(229,160,13,0.15) 0%, transparent 70%)",
          }}
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{
            scale: [0.5, 1.2, 1],
            opacity: [0, 0.8, 0.4],
          }}
          transition={{ duration: 1.5, ease: "easeOut" }}
        />

        {/* Secondary glow ring */}
        <motion.div
          className="absolute w-[400px] h-[400px] rounded-full border border-[#e5a00d]/20"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.3 }}
        />

        {/* Main content */}
        <div className="relative flex flex-col items-center">
          {/* Logo container */}
          <motion.div
            className="relative"
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{
              type: "spring",
              stiffness: 200,
              damping: 20,
              duration: 0.8,
            }}
          >
            {/* Outer rotating ring */}
            <motion.svg
              viewBox="0 0 120 120"
              className="absolute -inset-4 w-32 h-32"
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
            >
              <circle
                cx="60"
                cy="60"
                r="56"
                fill="none"
                stroke="#e5a00d"
                strokeWidth="1"
                strokeDasharray="8 12"
                opacity="0.3"
              />
            </motion.svg>

            {/* Main logo */}
            <motion.svg
              viewBox="0 0 120 120"
              className="w-24 h-24"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.5 }}
            >
              {/* Circle */}
              <motion.circle
                cx="60"
                cy="60"
                r="54"
                fill="none"
                stroke="#e5a00d"
                strokeWidth="4"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1, delay: 0.2, ease: "easeInOut" }}
              />
              {/* Play triangle */}
              <motion.path
                d="M48 38 L48 82 L90 60 Z"
                fill="#e5a00d"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.8, duration: 0.3, type: "spring" }}
              />
            </motion.svg>
          </motion.div>

          {/* Title */}
          <motion.div
            className="mt-8 flex flex-col items-center"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.6, duration: 0.5 }}
          >
            <motion.h1
              className="text-5xl font-bold tracking-[0.3em] text-white"
              initial={{ letterSpacing: "0.5em", opacity: 0 }}
              animate={{ letterSpacing: "0.3em", opacity: 1 }}
              transition={{ delay: 0.8, duration: 0.6 }}
            >
              TLEX
            </motion.h1>
            <motion.p
              className="mt-2 text-sm text-zinc-500 tracking-[0.2em] uppercase"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.2, duration: 0.5 }}
            >
              Your Media Server
            </motion.p>
          </motion.div>

          {/* Loading bar */}
          <motion.div
            className="mt-10 w-48 h-0.5 bg-zinc-800 rounded-full overflow-hidden"
            initial={{ opacity: 0, scaleX: 0 }}
            animate={{ opacity: 1, scaleX: 1 }}
            transition={{ delay: 1, duration: 0.3 }}
          >
            <motion.div
              className="h-full bg-gradient-to-r from-[#e5a00d] to-[#f5c842]"
              initial={{ x: "-100%" }}
              animate={{ x: "100%" }}
              transition={{
                delay: 1.2,
                duration: 1,
                ease: "easeInOut",
              }}
            />
          </motion.div>
        </div>

        {/* Particle effects */}
        {[...Array(6)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-1 h-1 rounded-full bg-[#e5a00d]"
            initial={{
              x: 0,
              y: 0,
              opacity: 0,
              scale: 0,
            }}
            animate={{
              x: Math.cos((i * 60 * Math.PI) / 180) * 150,
              y: Math.sin((i * 60 * Math.PI) / 180) * 150,
              opacity: [0, 1, 0],
              scale: [0, 1.5, 0],
            }}
            transition={{
              delay: 0.8 + i * 0.1,
              duration: 1.2,
              ease: "easeOut",
            }}
          />
        ))}
      </motion.div>
    </AnimatePresence>
  );
}
