package logasync

// PostHTTP is retained for win/bill notices that are already off the bid path.
func (w *Writer) PostHTTP(_ string, e Event) {
	w.Log(e)
}
