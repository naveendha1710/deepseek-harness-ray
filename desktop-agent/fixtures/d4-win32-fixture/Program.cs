using System;
using System.Runtime.InteropServices;
using System.IO;

internal static class Program
{
    const int WS_VISIBLE = 0x10000000, WS_CHILD = 0x40000000, WS_BORDER = 0x00800000;
    const int WS_OVERLAPPEDWINDOW = 0x00CF0000, BS_CHECKBOX = 2, BS_RADIOBUTTON = 4;
    const int WS_VSCROLL = 0x00200000, WS_TABSTOP = 0x00010000, CW_USEDEFAULT = unchecked((int)0x80000000);
    const int WM_CREATE = 1, WM_COMMAND = 0x111, BN_CLICKED = 0;
    const int IDC_EDIT = 101, IDC_BUTTON = 102, IDC_CHECK = 103, IDC_RADIO_A = 104, IDC_RADIO_B = 105;
    const int IDC_COMBO = 106, IDC_LIST = 107, IDC_TREE = 108, IDC_TABS = 109, IDC_STATUS = 110;

    delegate IntPtr WndProc(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] struct WNDCLASS
    {
        public uint style; public IntPtr lpfnWndProc; public int cbClsExtra, cbWndExtra;
        public IntPtr hInstance, hIcon, hCursor, hbrBackground, lpszMenuName, lpszClassName;
    }
    [DllImport("user32.dll", EntryPoint = "RegisterClassW", ExactSpelling = true)] static extern ushort RegisterClass(ref WNDCLASS value);
    [DllImport("user32.dll", EntryPoint = "CreateWindowExW", ExactSpelling = true, SetLastError = true)] static extern IntPtr CreateWindowEx(int ex, IntPtr className, IntPtr title, int style, int x, int y, int width, int height, IntPtr parent, IntPtr menu, IntPtr instance, IntPtr param);
    [DllImport("user32.dll", EntryPoint = "CreateWindowExW", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)] static extern IntPtr CreateWindowExText(int ex, string className, string title, int style, int x, int y, int width, int height, IntPtr parent, IntPtr menu, IntPtr instance, IntPtr param);
    [DllImport("kernel32.dll", SetLastError = true)] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool IsWindow(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr hwnd);
    [DllImport("user32.dll")] static extern IntPtr DefWindowProc(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll", EntryPoint = "SetWindowTextW", CharSet = CharSet.Unicode, ExactSpelling = true)] static extern bool SetWindowTextW(IntPtr hwnd, string text);
    [DllImport("user32.dll")] static extern int GetMessage(out MSG msg, IntPtr hwnd, uint min, uint max);
    [DllImport("user32.dll")] static extern bool TranslateMessage(ref MSG msg);
    [DllImport("user32.dll")] static extern IntPtr DispatchMessage(ref MSG msg);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern bool SetWindowText(IntPtr hwnd, string text);
    [DllImport("user32.dll", EntryPoint = "SendMessageW", ExactSpelling = true)] static extern IntPtr SendMessage(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
    [DllImport("kernel32.dll")] static extern IntPtr GetModuleHandle(string? name);
    [DllImport("comctl32.dll")] static extern bool InitCommonControlsEx(ref INITCOMMONCONTROLSEX value);
    [StructLayout(LayoutKind.Sequential)] struct INITCOMMONCONTROLSEX { public int dwSize, dwICC; }
    [StructLayout(LayoutKind.Sequential)] struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam, lParam; public uint time; public int x, y; }

    static IntPtr status, button;
    static WndProc? callback;
    static readonly string DiagnosticPath = Path.Combine(Path.GetTempPath(), "d4-native-msaa-fixture.log");

    static void Main()
    {
        try { File.WriteAllText(DiagnosticPath, "fixture_pid=" + Environment.ProcessId + " thread=" + GetCurrentThreadId() + Environment.NewLine); } catch { }
        var common = new INITCOMMONCONTROLSEX { dwSize = Marshal.SizeOf<INITCOMMONCONTROLSEX>(), dwICC = 0xFFFF };
        InitCommonControlsEx(ref common);
        callback = WindowProc;
        var instance = GetModuleHandle(null);
        var name = Marshal.StringToHGlobalUni("D4NativeMsaaFixtureClass");
        var windowClass = new WNDCLASS { lpfnWndProc = Marshal.GetFunctionPointerForDelegate(callback), hInstance = instance, lpszClassName = name };
        RegisterClass(ref windowClass);
        var title = Marshal.StringToHGlobalUni("D4 Native Win32 MSAA Fixture");
        var window = CreateWindowEx(0, name, title, WS_OVERLAPPEDWINDOW | WS_VISIBLE,
            CW_USEDEFAULT, CW_USEDEFAULT, 900, 700, IntPtr.Zero, IntPtr.Zero, instance, IntPtr.Zero);
        Log($"main hwnd={window} error={Marshal.GetLastWin32Error()} thread={GetCurrentThreadId()} created={IsWindow(window)} visible={IsWindowVisible(window)} enabled={IsWindowEnabled(window)}");
        SetWindowTextW(window, "D4 Native Win32 MSAA Fixture");
        CreateControls(window);
        var msg = new MSG();
        while (GetMessage(out msg, IntPtr.Zero, 0, 0) > 0) { TranslateMessage(ref msg); DispatchMessage(ref msg); }
        Marshal.FreeHGlobal(title);
        Marshal.FreeHGlobal(name);
    }

    static IntPtr WindowProc(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam)
    {
        if (message == WM_COMMAND && ((long)wParam >> 16 & 0xffff) == BN_CLICKED && ((int)wParam & 0xffff) == IDC_BUTTON)
            SetWindowText(status, "Button invoked");
        return DefWindowProc(hwnd, message, wParam, lParam);
    }

    static IntPtr Control(IntPtr parent, string className, string text, int id, int x, int y, int width, int height, int style = 0)
    {
        var fullStyle = WS_CHILD | WS_VISIBLE | WS_TABSTOP | WS_BORDER | style;
        var nativeClass = Marshal.StringToHGlobalUni(className);
        var nativeText = Marshal.StringToHGlobalUni(text);
        var child = CreateWindowEx(0, nativeClass, nativeText, fullStyle, x, y, width, height, parent, (IntPtr)id, GetModuleHandle(null), IntPtr.Zero);
        Marshal.FreeHGlobal(nativeClass);
        Marshal.FreeHGlobal(nativeText);
        Log($"control={className} id={id} hwnd={child} parent={parent} actual_parent={GetParent(child)} error={Marshal.GetLastWin32Error()} created={IsWindow(child)} parented={GetParent(child) == parent} visible={IsWindowVisible(child)} enabled={IsWindowEnabled(child)} style=0x{fullStyle:x} thread={GetCurrentThreadId()}");
        return child;
    }

    static void Log(string message)
    {
        try { File.AppendAllText(DiagnosticPath, DateTime.UtcNow.ToString("O") + " " + message + Environment.NewLine); } catch { }
    }

    static void CreateControls(IntPtr hwnd)
    {
        Control(hwnd, "STATIC", "D4 native MSAA fixture", 1, 20, 15, 300, 25);
        Control(hwnd, "STATIC", "Edit value", 2, 20, 55, 120, 25);
        Control(hwnd, "EDIT", "initial text", IDC_EDIT, 150, 52, 240, 28);
        button = Control(hwnd, "BUTTON", "Invoke button", IDC_BUTTON, 410, 52, 140, 28);
        Control(hwnd, "BUTTON", "Check me", IDC_CHECK, 20, 100, 120, 28, BS_CHECKBOX);
        Control(hwnd, "BUTTON", "Radio A", IDC_RADIO_A, 150, 100, 100, 28, BS_RADIOBUTTON);
        Control(hwnd, "BUTTON", "Radio B", IDC_RADIO_B, 260, 100, 100, 28, BS_RADIOBUTTON);
        var combo = Control(hwnd, "COMBOBOX", "", IDC_COMBO, 20, 150, 180, 100);
        Send(combo, 0x0143, "Choice A"); Send(combo, 0x0143, "Choice B"); Send(combo, 0x0143, "Choice C");
        var list = Control(hwnd, "LISTBOX", "", IDC_LIST, 220, 150, 180, 100);
        Send(list, 0x0180, "List A"); Send(list, 0x0180, "List B"); Send(list, 0x0180, "List C");
        Control(hwnd, "SysTreeView32", "", IDC_TREE, 420, 150, 200, 180);
        Control(hwnd, "SysTabControl32", "", IDC_TABS, 20, 280, 380, 180);
        status = Control(hwnd, "STATIC", "Status: ready", IDC_STATUS, 20, 500, 500, 30);
    }

    static void Send(IntPtr hwnd, uint message, string text)
    {
        var memory = Marshal.StringToHGlobalUni(text);
        try { SendMessage(hwnd, message, IntPtr.Zero, memory); } finally { Marshal.FreeHGlobal(memory); }
    }

    static void SendText(IntPtr hwnd, string text)
    {
        var memory = Marshal.StringToHGlobalUni(text);
        try { SendMessage(hwnd, 0x000C, IntPtr.Zero, memory); } finally { Marshal.FreeHGlobal(memory); }
    }
}
