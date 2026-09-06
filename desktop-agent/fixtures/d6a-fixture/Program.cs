using System.Drawing;
using System.Text.Json;
using System.Windows.Forms;

internal static class Program
{
    static string statePath = "";
    static Form form = null!;
    static Button button = null!;
    static CheckBox checkbox = null!;
    static TextBox text = null!;
    static Panel dragObject = null!;
    static Panel dragTarget = null!;
    static Panel scrollPanel = null!;
    static Label scrollMarker = null!;
    static int counter;
    static Point dragOffset;

    [STAThread]
    static void Main(string[] args)
    {
        statePath = args.Length == 0 ? Path.Combine(Path.GetTempPath(), "d6a-fixture.json") : args[0];
        ApplicationConfiguration.Initialize();
        form = new Form { Text = "D6A Coordinate Fixture", StartPosition = FormStartPosition.Manual, Location = new Point(180, 120), Size = new Size(900, 650), KeyPreview = true };
        form.KeyDown += (_, e) => { if (e.Control && e.KeyCode == Keys.K) { form.Text = "D6A Coordinate Fixture - Hotkey"; WriteState(); } };
        var title = new Label { Text = "D6A screen interaction fixture", Location = new Point(25, 20), AutoSize = true };
        form.Controls.Add(title);
        button = new Button { Text = "Counter: 0", Location = new Point(25, 60), Size = new Size(180, 60) };
        button.Click += (_, _) => { counter++; button.Text = $"Counter: {counter}"; WriteState(); };
        form.Controls.Add(button);
        checkbox = new CheckBox { Text = "Toggle me", Location = new Point(240, 80), AutoSize = true };
        checkbox.CheckedChanged += (_, _) => WriteState(); form.Controls.Add(checkbox);
        text = new TextBox { Text = "initial text", Location = new Point(25, 160), Size = new Size(280, 32) };
        text.TextChanged += (_, _) => WriteState(); form.Controls.Add(text);
        var textLabel = new Label { Text = "Text field", Location = new Point(25, 135), AutoSize = true }; form.Controls.Add(textLabel);
        dragTarget = new Panel { BackColor = Color.LightGreen, Location = new Point(650, 70), Size = new Size(120, 80) }; form.Controls.Add(dragTarget);
        dragObject = new Panel { BackColor = Color.CornflowerBlue, Location = new Point(500, 80), Size = new Size(100, 60) };
        dragObject.MouseDown += (_, e) => { if (e.Button == MouseButtons.Left) dragOffset = e.Location; };
        dragObject.MouseMove += (_, e) => { if (e.Button == MouseButtons.Left) { dragObject.Left += e.X - dragOffset.X; dragObject.Top += e.Y - dragOffset.Y; WriteState(); } };
        form.Controls.Add(dragObject);
        scrollPanel = new Panel { AutoScroll = true, BorderStyle = BorderStyle.FixedSingle, Location = new Point(25, 250), Size = new Size(300, 250) };
        scrollMarker = new Label { Text = "Scroll marker", Location = new Point(20, 20), BackColor = Color.Khaki, Size = new Size(180, 35) }; scrollPanel.Controls.Add(scrollMarker);
        for (var i = 0; i < 12; i++) scrollPanel.Controls.Add(new Label { Text = $"Scrollable label {i}", Location = new Point(20, 70 + i * 35), AutoSize = true });
        scrollPanel.Scroll += (_, _) => WriteState(); form.Controls.Add(scrollPanel);
        form.Shown += (_, _) => WriteState();
        Application.Run(form);
    }

    static Rectangle ScreenRect(Control control) => new(form.PointToScreen(control.Location), control.Size);

    static void WriteState()
    {
        var state = new {
            ready = form.IsHandleCreated, title = form.Text, counter, checked_state = checkbox.Checked,
            text = text.Text, drag_object = ScreenRect(dragObject), drag_target = ScreenRect(dragTarget),
            scroll_value = scrollPanel.VerticalScroll.Value, button = ScreenRect(button), checkbox = ScreenRect(checkbox),
            text_rect = ScreenRect(text), scroll_region = ScreenRect(scrollPanel), screen = Screen.PrimaryScreen?.Bounds
        };
        var json = JsonSerializer.Serialize(state);
        var temporary = statePath + ".tmp"; File.WriteAllText(temporary, json); File.Move(temporary, statePath, true);
    }
}
