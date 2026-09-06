using System.Drawing;
using System.Windows.Forms;

namespace D3CUiaFixture;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new FixtureForm());
    }
}

internal sealed class FixtureForm : Form
{
    private readonly Label _state = new();
    private readonly TextBox _text = new();
    private readonly CheckBox _check = new();
    private readonly ComboBox _combo = new();
    private readonly ListBox _list = new();
    private readonly TreeView _tree = new();
    private readonly TabControl _tabs = new();
    private readonly Panel _scroll = new();

    public FixtureForm()
    {
        Name = "D3C_FixtureWindow";
        AccessibleName = "D3C UIA Fixture Window";
        Text = "D3C UIA Fixture";
        Width = 1000;
        Height = 760;
        StartPosition = FormStartPosition.CenterScreen;

        var layout = new TableLayoutPanel
        {
            Name = "D3C_MainLayout",
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 9,
            Padding = new Padding(12),
            AutoScroll = true,
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 190));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(layout);

        AddLabel(layout, "D3C_StatusLabel", "Fixture state", 0);
        _state.Name = "D3C_StateValue";
        _state.AccessibleName = "Fixture state value";
        _state.Text = "Ready";
        _state.AutoSize = true;
        layout.Controls.Add(_state, 1, 0);

        AddLabel(layout, "D3C_TextLabel", "Text input", 1);
        _text.Name = "D3C_TextBox";
        _text.AccessibleName = "D3C text input";
        _text.Text = "initial text";
        _text.Width = 300;
        layout.Controls.Add(_text, 1, 1);

        AddLabel(layout, "D3C_ButtonLabel", "Invoke button", 2);
        var button = new Button
        {
            Name = "D3C_InvokeButton",
            AccessibleName = "D3C invoke button",
            Text = "Invoke safely",
            AutoSize = true,
        };
        button.Click += (_, _) => _state.Text = "Button invoked";
        layout.Controls.Add(button, 1, 2);

        AddLabel(layout, "D3C_CheckLabel", "Checkbox / toggle", 3);
        _check.Name = "D3C_CheckBox";
        _check.AccessibleName = "D3C checkbox toggle";
        _check.Text = "Enabled fixture option";
        layout.Controls.Add(_check, 1, 3);

        AddLabel(layout, "D3C_ComboLabel", "Combo box", 4);
        _combo.Name = "D3C_ComboBox";
        _combo.AccessibleName = "D3C combo selection";
        _combo.DropDownStyle = ComboBoxStyle.DropDownList;
        _combo.Items.AddRange(new object[] { "Red", "Green", "Blue" });
        _combo.SelectedIndex = 0;
        layout.Controls.Add(_combo, 1, 4);

        AddLabel(layout, "D3C_ListLabel", "List", 5);
        _list.Name = "D3C_ListBox";
        _list.AccessibleName = "D3C list selection";
        _list.Items.AddRange(new object[] { "Alpha", "Beta", "Gamma" });
        _list.SelectedIndex = 0;
        _list.Height = 70;
        layout.Controls.Add(_list, 1, 5);

        AddLabel(layout, "D3C_TreeLabel", "Tree", 6);
        _tree.Name = "D3C_TreeView";
        _tree.AccessibleName = "D3C tree navigation";
        var root = _tree.Nodes.Add("Root");
        root.Name = "D3C_RootNode";
        root.Nodes.Add("Child").Name = "D3C_ChildNode";
        _tree.Height = 90;
        layout.Controls.Add(_tree, 1, 6);

        AddLabel(layout, "D3C_TabLabel", "Tabs", 7);
        _tabs.Name = "D3C_TabControl";
        _tabs.AccessibleName = "D3C tab selection";
        _tabs.TabPages.Add(new TabPage("First") { Name = "D3C_FirstTab" });
        _tabs.TabPages.Add(new TabPage("Second") { Name = "D3C_SecondTab" });
        _tabs.Height = 90;
        layout.Controls.Add(_tabs, 1, 7);

        AddLabel(layout, "D3C_ScrollLabel", "Scroll region", 8);
        _scroll.Name = "D3C_ScrollViewer";
        _scroll.AccessibleName = "D3C scroll region";
        _scroll.AutoScroll = true;
        _scroll.BorderStyle = BorderStyle.FixedSingle;
        _scroll.Height = 100;
        for (var index = 0; index < 15; index++)
        {
            _scroll.Controls.Add(new Label
            {
                Name = $"D3C_ScrollText_{index}",
                AccessibleName = $"D3C scroll text {index}",
                Text = $"Scrollable fixture row {index}",
                AutoSize = true,
                Location = new Point(8, index * 24),
            });
        }
        layout.Controls.Add(_scroll, 1, 8);

        var menu = new MenuStrip { Name = "D3C_Menu" };
        var menuItem = new ToolStripMenuItem("Safe action")
        {
            Name = "D3C_SafeMenuItem",
            AccessibleName = "D3C safe menu action",
        };
        menuItem.Click += (_, _) => _state.Text = "Menu invoked";
        menu.Items.Add(menuItem);
        MainMenuStrip = menu;
        Controls.Add(menu);
    }

    private static void AddLabel(TableLayoutPanel layout, string name, string text, int row)
    {
        layout.Controls.Add(new Label
        {
            Name = name,
            AccessibleName = name,
            Text = text,
            AutoSize = true,
        }, 0, row);
    }
}
