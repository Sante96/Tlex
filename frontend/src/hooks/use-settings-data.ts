"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getWorkersStatus,
  getSystemStats,
  getAutoScanStatus,
  getScannerStatus,
  triggerManualScan,
  getRegistrationStatus,
  setRegistrationStatus,
  listUsers,
  type WorkersStatusResponse,
  type SystemStats,
  type AutoScanStatus,
  type ScanStatus,
  type UserInfo,
} from "@/lib/api";

export function useSettingsData(isAdmin: boolean) {
  const [workersData, setWorkersData] = useState<WorkersStatusResponse | null>(
    null,
  );
  const [statsData, setStatsData] = useState<SystemStats | null>(null);
  const [autoScanData, setAutoScanData] = useState<AutoScanStatus | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [loadingWorkers, setLoadingWorkers] = useState(false);
  const [loadingStats, setLoadingStats] = useState(false);
  const [loadingScan, setLoadingScan] = useState(false);
  const [triggeringScan, setTriggeringScan] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState<boolean | null>(
    null,
  );
  const [togglingRegistration, setTogglingRegistration] = useState(false);
  const [usersData, setUsersData] = useState<UserInfo[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  const loadWorkersStatus = useCallback(async () => {
    try {
      setLoadingWorkers(true);
      setWorkersData(await getWorkersStatus());
    } catch {
    } finally {
      setLoadingWorkers(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      setLoadingStats(true);
      setStatsData(await getSystemStats());
    } catch {
    } finally {
      setLoadingStats(false);
    }
  }, []);

  const loadScanStatus = useCallback(async () => {
    try {
      setLoadingScan(true);
      const [autoScan, status] = await Promise.all([
        getAutoScanStatus(),
        getScannerStatus(),
      ]);
      setAutoScanData(autoScan);
      setScanStatus(status);
    } catch {
    } finally {
      setLoadingScan(false);
    }
  }, []);

  const handleTriggerScan = useCallback(async () => {
    try {
      setTriggeringScan(true);
      await triggerManualScan();
      await loadScanStatus();
    } catch {
    } finally {
      setTriggeringScan(false);
    }
  }, [loadScanStatus]);

  const loadRegistrationStatus = useCallback(async () => {
    try {
      const data = await getRegistrationStatus();
      setRegistrationOpen(data.enabled);
    } catch {}
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      setLoadingUsers(true);
      setUsersData(await listUsers());
    } catch {
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  const handleToggleRegistration = useCallback(async () => {
    if (registrationOpen === null) return;
    setTogglingRegistration(true);
    try {
      const data = await setRegistrationStatus(!registrationOpen);
      setRegistrationOpen(data.enabled);
    } catch {}
    setTogglingRegistration(false);
  }, [registrationOpen]);

  useEffect(() => {
    if (isAdmin) {
      loadWorkersStatus();
      loadStats();
      loadScanStatus();
      loadRegistrationStatus();
      loadUsers();
    }
  }, [
    isAdmin,
    loadWorkersStatus,
    loadStats,
    loadScanStatus,
    loadRegistrationStatus,
    loadUsers,
  ]);

  return {
    workersData,
    statsData,
    autoScanData,
    setAutoScanData,
    scanStatus,
    loadingWorkers,
    loadingStats,
    loadingScan,
    triggeringScan,
    registrationOpen,
    togglingRegistration,
    usersData,
    loadingUsers,
    loadWorkersStatus,
    loadStats,
    loadScanStatus,
    handleTriggerScan,
    handleToggleRegistration,
    loadUsers,
  };
}
