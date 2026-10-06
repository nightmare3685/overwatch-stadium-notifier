// WASAPI process-loopback bridge. stdout: 16 kHz mono signed 16-bit PCM.
// Uses Windows public audio APIs; does not inject into the game.
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

[ComImport, Guid("72A22D78-CDE4-431D-B8CC-843A71199B6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IActivation {
    [PreserveSig] int GetActivateResult(out int result, [MarshalAs(UnmanagedType.IUnknown)] out object client);
}
[Guid("41D949AB-9862-444A-80F6-C261334DA5EB"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface ICompletion { [PreserveSig] int ActivateCompleted(IActivation operation); }
[Guid("94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAgileObject { }
[ComVisible(true), ClassInterface(ClassInterfaceType.None)]
public class Completion : ICompletion, IAgileObject {
    public readonly ManualResetEvent Ready = new ManualResetEvent(false);
    public object Client;
    public int Result;
    public int ActivateCompleted(IActivation operation) {
        try { int hr = operation.GetActivateResult(out Result, out Client); if (hr < 0) Result = hr; }
        catch (Exception e) { Result = Marshal.GetHRForException(e); }
        finally { Ready.Set(); }
        return 0;
    }
}
[StructLayout(LayoutKind.Sequential, Pack=2)]
public struct WaveFormat {
    public ushort tag, channels;
    public uint rate, bytesPerSecond;
    public ushort blockAlign, bits, extra;
}
[StructLayout(LayoutKind.Explicit, Size=24)]
public struct PropVariant {
    [FieldOffset(0)] public ushort type;
    [FieldOffset(8)] public uint size;
    [FieldOffset(16)] public IntPtr data;
}
[ComImport, Guid("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioClient {
    [PreserveSig] int Initialize(int mode, uint flags, long duration, long periodicity, ref WaveFormat format, IntPtr session);
    [PreserveSig] int GetBufferSize(out uint frames);
    [PreserveSig] int GetStreamLatency(out long latency);
    [PreserveSig] int GetCurrentPadding(out uint frames);
    [PreserveSig] int IsFormatSupported(int mode, IntPtr format, IntPtr closest);
    [PreserveSig] int GetMixFormat(out IntPtr format);
    [PreserveSig] int GetDevicePeriod(out long normal, out long minimum);
    [PreserveSig] int Start();
    [PreserveSig] int Stop();
    [PreserveSig] int Reset();
    [PreserveSig] int SetEventHandle(IntPtr handle);
    [PreserveSig] int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object service);
}
[ComImport, Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface ICapture {
    [PreserveSig] int GetBuffer(out IntPtr data, out uint frames, out uint flags, out ulong position, out ulong clock);
    [PreserveSig] int ReleaseBuffer(uint frames);
    [PreserveSig] int GetNextPacketSize(out uint frames);
}
public class Program {
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    struct VersionInfo {
        public uint size, major, minor, build, platform;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string servicePack;
    }
    [DllImport("ntdll.dll", CharSet=CharSet.Unicode)]
    static extern int RtlGetVersion(ref VersionInfo version);
    [DllImport("Mmdevapi.dll", CharSet=CharSet.Unicode, ExactSpelling=true)]
    static extern int ActivateAudioInterfaceAsync(string path, ref Guid iid, ref PropVariant parameters,
        ICompletion completion, out IActivation operation);
    static volatile bool stopping;
    static void Check(int hr) { if (hr < 0) Marshal.ThrowExceptionForHR(hr); }
    [MTAThread]
    public static int Main(string[] args) {
        Console.OutputEncoding = new System.Text.UTF8Encoding(false);
        try {
            if (args.Length == 1 && args[0] == "--list") {
                foreach (Process p in Process.GetProcessesByName("Overwatch")) {
                    Console.WriteLine(p.Id); p.Dispose();
                }
                return 0;
            }
            VersionInfo version = new VersionInfo(); version.size = (uint)Marshal.SizeOf(version);
            Check(RtlGetVersion(ref version));
            if (!Environment.Is64BitProcess || version.build < 20348)
                throw new NotSupportedException("Requires 64-bit Windows build 20348+ (Windows 11 recommended).");
            int pid;
            if (args.Length != 1 || !int.TryParse(args[0], out pid) || pid <= 0)
                throw new ArgumentException("Expected a target process ID.");
            using (Process target = Process.GetProcessById(pid)) {
                // Pin the handle, so reuse of the PID cannot silently select another app.
                IntPtr targetHandle = OpenProcess(0x100000, false, pid); // SYNCHRONIZE only
                if (targetHandle == IntPtr.Zero) throw new System.ComponentModel.Win32Exception();
                try { return Capture(target, targetHandle); }
                finally { CloseHandle(targetHandle); }
            }
        } catch (Exception e) { Console.Error.WriteLine("ERROR: " + e.Message); return 1; }
    }
    static int Capture(Process target, IntPtr targetHandle) {
        IntPtr parameters = Marshal.AllocHGlobal(12);
        IActivation operation = null;
        IAudioClient client = null;
        ICapture capture = null;
        Completion completion = new Completion();
        using (AutoResetEvent available = new AutoResetEvent(false)) {
            try {
                Marshal.WriteInt32(parameters, 0, 1); // PROCESS_LOOPBACK activation
                Marshal.WriteInt32(parameters, 4, target.Id);
                Marshal.WriteInt32(parameters, 8, 0); // INCLUDE_TARGET_PROCESS_TREE
                PropVariant variant = new PropVariant { type=65, size=12, data=parameters };
                Guid iid = typeof(IAudioClient).GUID;
                Check(ActivateAudioInterfaceAsync("VAD\\Process_Loopback", ref iid, ref variant, completion, out operation));
                if (!completion.Ready.WaitOne(10000)) throw new TimeoutException("Audio activation timed out.");
                Check(completion.Result);
                client = (IAudioClient)completion.Client;
                WaveFormat format = new WaveFormat { tag=1, channels=1, rate=16000,
                    bytesPerSecond=32000, blockAlign=2, bits=16, extra=0 };
                Check(client.Initialize(0, 0x80060000, 0, 0, ref format, IntPtr.Zero));
                Check(client.SetEventHandle(available.SafeWaitHandle.DangerousGetHandle()));
                Guid captureId = typeof(ICapture).GUID;
                object service;
                Check(client.GetService(ref captureId, out service));
                capture = (ICapture)service;
                Check(client.Start());
                Console.Error.WriteLine("READY " + target.Id);
                Thread input = new Thread(delegate() { Console.ReadLine(); stopping = true; });
                input.IsBackground = true; input.Start();
                Stream output = Console.OpenStandardOutput();
                bool firstPacket = true;
                while (!stopping) {
                    if (WaitForSingleObject(targetHandle, 0) == 0) throw new InvalidOperationException("Target process exited. Restart detection after launching Overwatch.");
                    available.WaitOne(100);
                    uint next;
                    Check(capture.GetNextPacketSize(out next));
                    while (next > 0) {
                        IntPtr data; uint frames, flags; ulong position, clock;
                        Check(capture.GetBuffer(out data, out frames, out flags, out position, out clock));
                        try {
                            if ((flags & 1) != 0 && !firstPacket)
                                throw new IOException("Audio discontinuity. Stop and restart detection.");
                            byte[] buffer = new byte[checked((int)frames * 2)];
                            if ((flags & 2) == 0) Marshal.Copy(data, buffer, 0, buffer.Length);
                            output.Write(buffer, 0, buffer.Length);
                            output.Flush();
                            firstPacket = false;
                        } finally { Check(capture.ReleaseBuffer(frames)); }
                        Check(capture.GetNextPacketSize(out next));
                    }
                }
                return 0;
            } finally {
                if (client != null) client.Stop();
                if (capture != null) Marshal.ReleaseComObject(capture);
                if (client != null) Marshal.ReleaseComObject(client);
                if (operation != null) Marshal.ReleaseComObject(operation);
                Marshal.FreeHGlobal(parameters);
                GC.KeepAlive(completion);
            }
        }
    }
}
