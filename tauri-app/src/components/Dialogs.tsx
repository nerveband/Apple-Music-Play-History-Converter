import { Dialog } from "./ui/Dialog";
import { Button } from "./ui/Button";

interface ConfirmDialog {
  open: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

interface DialogsProps {
  showHowTo: boolean;
  onCloseHowTo: () => void;
  showAbout: boolean;
  onCloseAbout: () => void;
  confirm?: ConfirmDialog | null;
}

export function Dialogs({ showHowTo, onCloseHowTo, showAbout, onCloseAbout, confirm }: DialogsProps) {
  return (
    <>
      <Dialog
        open={showHowTo}
        onClose={onCloseHowTo}
        title="How to Use"
        width="lg"
      >
        <ol className="list-decimal pl-5 space-y-2 text-sm">
          <li>Select your Apple Music CSV export.</li>
          <li>Pick a search provider (MusicBrainz or iTunes).</li>
          <li>Start search and wait for matches.</li>
          <li>Export results in your preferred format.</li>
        </ol>
      </Dialog>

      <Dialog
        open={showAbout}
        onClose={onCloseAbout}
        title="About"
        width="md"
      >
        <div className="text-sm space-y-2">
          <div>Apple Music History Converter</div>
          <div>Built with Tauri, React, and Python sidecar.</div>
        </div>
      </Dialog>

      {confirm && (
        <Dialog
          open={confirm.open}
          onClose={confirm.onCancel}
          title={confirm.title}
          footer={
            <>
              <Button variant="ghost" onClick={confirm.onCancel}>Cancel</Button>
              <Button onClick={confirm.onConfirm}>Confirm</Button>
            </>
          }
        >
          <div className="text-sm">{confirm.message}</div>
        </Dialog>
      )}
    </>
  );
}
