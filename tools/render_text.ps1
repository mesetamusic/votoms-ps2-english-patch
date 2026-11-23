# Renders one line of text to a 32-bit PNG with transparent background.
# usage: render_text.ps1 -Text "..." -Height 16 -Out file.png [-Font "Arial"] [-Bold] [-Italic] [-Outline 1]
param([string]$Text, [int]$Height, [string]$Out, [string]$Font = "Arial", [switch]$Bold, [switch]$Italic, [int]$Outline = 0)
Add-Type -AssemblyName System.Drawing
$style = [System.Drawing.FontStyle]::Regular
if ($Bold) { $style = $style -bor [System.Drawing.FontStyle]::Bold }
if ($Italic) { $style = $style -bor [System.Drawing.FontStyle]::Italic }
$fam = New-Object System.Drawing.FontFamily($Font)
$em = $Height * $fam.GetEmHeight($style) / $fam.GetCellAscent($style) * 0.98
$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$fmt = [System.Drawing.StringFormat]::GenericTypographic
$path.AddString($Text, $fam, [int]$style, [single]$em, (New-Object System.Drawing.PointF(0, 0)), $fmt)
$b = $path.GetBounds()
$pad = $Outline + 2
$w = [int][Math]::Ceiling($b.Width) + 2 * $pad; $h = [int][Math]::Ceiling($b.Height) + 2 * $pad
$m = New-Object System.Drawing.Drawing2D.Matrix
$m.Translate(-$b.X + $pad, -$b.Y + $pad)
$path.Transform($m)
$bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::Transparent)
if ($Outline -gt 0) {
  $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::Black, [single](2 * $Outline))
  $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  $g.DrawPath($pen, $path)
}
$g.FillPath([System.Drawing.Brushes]::White, $path)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
"$w $h"
