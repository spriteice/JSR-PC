// What Ghidra has at each address in a list, for tools/recovery_crosscheck.py.
//
//   analyzeHeadless <proj> <name> -process jetsetradio.exe -noanalysis -readOnly \
//       -scriptPath tools/ghidra -postScript RecoveryFacts.java <addresses.txt> <facts.tsv>
//
// addresses.txt holds one hex address per line. One row per address, tab-separated:
//   addr      the address, as given
//   listing   instr (an instruction starts here), midinstr (inside one), data
//             (inside defined data) or undef (nothing decoded)
//   dtype     the data type's name when listing is data, else -
//   func      the entry of the function whose body holds it, or -
//   fname     the name of the function that starts here, or -
//   refs      references to the address, then by kind: call, jump, data, other
//   from      the first referring address, or -
// Metadata only: no instruction text or bytes are written.
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class RecoveryFacts extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        if (a.length < 2) {
            printerr("usage: RecoveryFacts.java <addresses.txt> <facts.tsv>");
            return;
        }
        Listing listing = currentProgram.getListing();
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();
        int rows = 0;
        try (BufferedReader in = new BufferedReader(new FileReader(a[0]));
             PrintWriter out = new PrintWriter(new FileWriter(a[1]))) {
            out.println("addr\tlisting\tdtype\tfunc\tfname\trefs\tcall\tjump\tdata\tother\tfrom");
            String line;
            while ((line = in.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                Address ad = toAddr(Long.parseLong(line.replace("0x", ""), 16));
                String kind, dtype = "-";
                if (listing.getInstructionAt(ad) != null) kind = "instr";
                else if (listing.getInstructionContaining(ad) != null) kind = "midinstr";
                else {
                    Data d = listing.getDefinedDataContaining(ad);
                    kind = d != null ? "data" : "undef";
                    if (d != null) dtype = d.getDataType().getName().replace('\t', ' ');
                }
                Function f = fm.getFunctionContaining(ad);
                Function at = fm.getFunctionAt(ad);
                int n = 0, call = 0, jump = 0, data = 0, other = 0;
                String from = "-";
                for (Reference r : rm.getReferencesTo(ad)) {
                    n++;
                    RefType t = r.getReferenceType();
                    if (t.isCall()) call++;
                    else if (t.isJump()) jump++;
                    else if (t.isData()) data++;
                    else other++;
                    if (from.equals("-")) from = r.getFromAddress().toString();
                }
                out.println(line + "\t" + kind + "\t" + dtype + "\t"
                        + (f == null ? "-" : f.getEntryPoint().toString()) + "\t"
                        + (at == null ? "-" : at.getName().replace('\t', ' ')) + "\t"
                        + n + "\t" + call + "\t" + jump + "\t" + data + "\t" + other + "\t" + from);
                rows++;
            }
        }
        println("RecoveryFacts: " + rows + " addresses -> " + a[1]);
    }
}
