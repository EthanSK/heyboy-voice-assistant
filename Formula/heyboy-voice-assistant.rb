class HeyboyVoiceAssistant < Formula
  desc "Works with any of your AI subscriptions."
  homepage "https://github.com/EthanSK/heyboy-voice-assistant"
  license "MIT"

  # Interim HEAD-only formula until tagged releases are cut.
  head "https://github.com/EthanSK/heyboy-voice-assistant.git", branch: "main"

  depends_on "python@3.11"

  def install
    libexec.install Dir["*"]

    (bin/"heyboy").write_env_script(
      libexec/"scripts/heyboy",
      {
        "HEYBOY_PROJECT_ROOT" => libexec,
        "PATH" => "#{Formula["python@3.11"].opt_bin}:#{ENV["PATH"]}"
      }
    )
  end

  def caveats
    <<~EOS
      heyboy voice assistant installed.

      First-time setup:
        heyboy install
        heyboy setup openclaw --api-key "YOUR_TOKEN"
        heyboy doctor
        heyboy run

      Launch as background app/daemon:
        heyboy app install
        heyboy app start
    EOS
  end

  test do
    assert_match "heyboy voice assistant CLI", shell_output("#{bin}/heyboy --help")
  end
end
